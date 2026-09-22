import json
import re

import pandas as pd
import plotly.express as px

COR_LINHA_DESEMPENHO = "#4472c4"
COR_LINHA_OBJETIVO = "#ff4b4b"

# O dia na Wheaton começa às 06:00 e termina às 05:59 do dia seguinte.
HORA_INICIO_DIA_WHEATON = 6

# A coluna "Hora Hora Wht (6to6)" marca o fim do bloco de uma hora, então o
# primeiro bloco do dia (06:00 às 07:00) vem rotulado como 7.
PRIMEIRA_HORA_HORA_WHEATON = 7

# Coluna auxiliar de ordenação, sempre removida antes de devolver os dados.
_COLUNA_ORDEM_WHEATON = "_ordem_dia_wheaton"

# Colunas usadas na análise de desvios; sem elas o arquivo enviado não serve.
COLUNAS_DESVIOS = (
    "OP Vertech",
    "Desvio sigla",
    "Localizacao",
    "Qtd Amostra (corrigido)",
    "Qtd Defeito",
)


def process_excel_producao(excel_file):
    df = pd.read_excel(excel_file)
    df = adjust_columns(df)
    df = adjust_float(df)

    desempenho_empacotamento_diario = get_desempenho_diario(df)
    desempenho_hora_hora = get_desempenho_hora_hora(df)

    return desempenho_empacotamento_diario, desempenho_hora_hora


def process_excel_notas(excel_file) -> pd.DataFrame:
    """Bloco de notas: o cabeçalho real está na segunda linha da planilha."""
    df_notas = pd.read_excel(excel_file)
    df_notas = df_notas.drop(columns=["Unnamed: 1"], errors="ignore")
    df_notas.columns = df_notas.iloc[1]
    df_notas = df_notas.iloc[2:].reset_index(drop=True)
    df_notas.columns.name = None

    return df_notas


def process_excel_desvios(excel_file) -> pd.DataFrame:
    """Desvios por máquina: o cabeçalho começa na terceira linha da planilha."""
    df_desvios = pd.read_excel(excel_file, header=2)

    colunas_faltando = [
        coluna
        for coluna in COLUNAS_DESVIOS
        if coluna not in df_desvios.columns
    ]

    if colunas_faltando:
        raise ValueError(
            "Colunas não encontradas no excel de desvios: "
            + ", ".join(colunas_faltando)
        )

    return df_desvios


def get_maquinas_abaixo_objetivo(desempenho: pd.DataFrame) -> list[str]:
    """Máquinas cujo empacotado menos rejeitado ficou abaixo do objetivo."""
    desempenho_exibicao = desempenho.reset_index()

    maquinas = desempenho_exibicao.loc[
        desempenho_exibicao["Emp - Rejeitado %"]
        < desempenho_exibicao["Objetivo %"],
        "Maquina",
    ]

    return maquinas.dropna().drop_duplicates().tolist()


def separar_data_hora(df_notas: pd.DataFrame) -> pd.DataFrame:
    """
    Para exibição: quebra a coluna 'Hora' (datetime) em 'Data' no formato
    brasileiro e 'Hora' apenas com o horário, mantendo a posição original.
    """
    if "Hora" not in df_notas.columns:
        return df_notas

    notas = df_notas.copy()
    data_hora = pd.to_datetime(notas["Hora"], errors="coerce")

    notas["Hora"] = data_hora.dt.strftime("%H:%M:%S")
    notas.insert(
        notas.columns.get_loc("Hora"),
        "Data",
        data_hora.dt.strftime("%d/%m/%Y"),
    )

    return notas


def ordenar_notas_por_dia_wheaton(df_notas: pd.DataFrame) -> pd.DataFrame:
    """
    Ordena as anotações pelo dia Wheaton, das 06:00 às 05:59 do dia seguinte.

    As notas da madrugada (00:00 às 05:59) pertencem ao fim do dia, e não ao
    começo — no bloco de notas elas vêm com a mesma data das notas da manhã,
    então ordenar pela data/hora bruta jogaria a madrugada para o início.
    """
    if "Hora" not in df_notas.columns:
        return df_notas

    data_hora = pd.to_datetime(df_notas["Hora"], errors="coerce")

    ordem = (
        ((data_hora.dt.hour - HORA_INICIO_DIA_WHEATON) % 24) * 3600
        + data_hora.dt.minute * 60
        + data_hora.dt.second
    )

    return (
        df_notas.assign(**{_COLUNA_ORDEM_WHEATON: ordem})
        .sort_values(_COLUNA_ORDEM_WHEATON, kind="stable", na_position="last")
        .drop(columns=_COLUNA_ORDEM_WHEATON)
        .reset_index(drop=True)
    )


def ordenar_prefixos_por_troca(
    desempenho_hora_hora: pd.DataFrame | None,
    maquina,
    prefixos: list | None = None,
) -> list[str]:
    """
    Prefixos de uma máquina na ordem em que rodaram no dia Wheaton.

    Quando houve troca de máquina (setup), o prefixo que saiu rodou nas
    primeiras horas do dia e por isso vem antes do que entrou. Prefixos sem
    dados hora a hora ficam no fim, em ordem alfabética.
    """
    primeira_hora = _primeira_hora_por_prefixo(desempenho_hora_hora, maquina)

    if prefixos is None:
        prefixos = list(primeira_hora)

    nomes = list(dict.fromkeys(str(prefixo) for prefixo in prefixos))

    return sorted(nomes, key=lambda nome: (primeira_hora.get(nome, 24), nome))


def _primeira_hora_por_prefixo(
    desempenho_hora_hora: pd.DataFrame | None,
    maquina,
) -> dict[str, int]:
    """Posição da primeira hora Wheaton em que cada prefixo da máquina rodou."""
    if desempenho_hora_hora is None or desempenho_hora_hora.empty:
        return {}

    linhas = desempenho_hora_hora.loc[
        desempenho_hora_hora["Maquina"].astype("string") == str(maquina)
    ].copy()

    if linhas.empty:
        return {}

    horas = pd.to_numeric(linhas["Hora Hora Wht (6to6)"], errors="coerce")

    linhas["Prefixo"] = linhas["Prefixo"].astype("string")
    linhas[_COLUNA_ORDEM_WHEATON] = (horas - PRIMEIRA_HORA_HORA_WHEATON) % 24
    linhas = linhas.dropna(subset=["Prefixo", _COLUNA_ORDEM_WHEATON])

    return {
        str(prefixo): int(ordem)
        for prefixo, ordem in linhas.groupby("Prefixo")[_COLUNA_ORDEM_WHEATON]
        .min()
        .items()
    }


def adjust_columns(df: pd.DataFrame):
    """
        Cabeçalho da tabela na 3 linha
    """
    df.columns = df.iloc[1]
    df = df.iloc[2:].reset_index(drop=True)
    df.columns.name = None

    return df


def adjust_float(df: pd.DataFrame):
    colunas_float = [
        "Eficiencia Plan",
        "Hora Hora Wht (6to6)",
        "Veloc Stand",
        "Veloc Real",
        "Qtd Teorica Real",
        "Corte de Gota %",
        "Objetivo %",
        "Qtd Objetivo",
        "Empacotado %",
        "Qtd Empacotado",
        "Qtd Rejeicao",
        "Rejeição %",
    ]

    for coluna in colunas_float:
        df[coluna] = pd.to_numeric(
            df[coluna]
            .astype("string")
            .str.strip()
            .str.replace("%", "", regex=False)
            .str.replace(",", ".", regex=False),
            errors="coerce",
        )
    return df


def get_desempenho_diario(df: pd.DataFrame):
    desempenho_empacotamento_diario = df.groupby(["Maquina", "Prefixo"]).agg({
        "OP Vertech": "first",
        "Objetivo %": "first",
        "Empacotado %": "mean",
        "Rejeição %": "mean",
    })

    desempenho_empacotamento_diario["Emp - Rejeitado %"] = (
        desempenho_empacotamento_diario["Empacotado %"]
        * (1 - desempenho_empacotamento_diario["Rejeição %"])
    )

    colunas_percentuais = [
        "Objetivo %",
        "Empacotado %",
        "Rejeição %",
        "Emp - Rejeitado %",
    ]

    desempenho_empacotamento_diario[colunas_percentuais] = (
        desempenho_empacotamento_diario[colunas_percentuais]
        .mul(100)
        .round(2)
    )

    return desempenho_empacotamento_diario


def get_desempenho_hora_hora(df: pd.DataFrame):
    return (
        df.groupby(
            ["Maquina", "Hora Hora Wht (6to6)", "Prefixo"],
            as_index=False,
        )
        .agg({
            "Objetivo %": "first",
            "Empacotado %": "first",
            "Rejeição %": "mean",
        })
        .dropna(
            subset=[
                "Maquina",
                "Hora Hora Wht (6to6)",
                "Prefixo",
                "Empacotado %",
            ]
        )
    )


def gerar_json_anotacoes_por_maquina(
    df_notas: pd.DataFrame,
    maquinas_selecionadas: list[str],
) -> str:
    """
    JSON somente com as anotações das máquinas selecionadas — é o que é enviado
    para a IA. Quando as notas têm a coluna 'Prefixo', agrupa por prefixo.

    As anotações vão ordenadas pelo dia Wheaton (06:00 às 05:59) e, por
    consequência, os prefixos aparecem na ordem em que rodaram na máquina.
    """
    if "Maquina" not in df_notas.columns:
        raise ValueError("A coluna 'Maquina' não foi encontrada nas anotações.")

    notas_tem_prefixo = "Prefixo" in df_notas.columns
    maquinas_sem_repeticao = list(dict.fromkeys(maquinas_selecionadas))
    notas_ordenadas = ordenar_notas_por_dia_wheaton(df_notas)
    anotacoes_por_maquina = {}

    for maquina in maquinas_sem_repeticao:
        anotacoes_maquina = notas_ordenadas.loc[
            notas_ordenadas["Maquina"] == maquina
        ]

        if notas_tem_prefixo:
            anotacoes_por_maquina[str(maquina)] = {
                str(prefixo): _registros_anotacoes(anotacoes_prefixo)
                for prefixo, anotacoes_prefixo in anotacoes_maquina.groupby(
                    anotacoes_maquina["Prefixo"].astype("string").fillna("Sem prefixo"),
                    sort=False,
                )
            }
        else:
            anotacoes_por_maquina[str(maquina)] = _registros_anotacoes(
                anotacoes_maquina
            )

    return json.dumps(anotacoes_por_maquina, ensure_ascii=False, indent=2, default=str)


def gerar_grafico_desempenho_hora_hora(
    desempenho_hora_hora: pd.DataFrame,
    maquina: str,
    prefixo: str,
):
    dados_grafico = desempenho_hora_hora.loc[
        (desempenho_hora_hora["Maquina"] == maquina)
        & (desempenho_hora_hora["Prefixo"] == prefixo)
    ].copy()

    if dados_grafico.empty:
        raise ValueError(
            f"Não há dados hora a hora para a máquina {maquina} e o prefixo {prefixo}."
        )

    dados_grafico["Ordem Hora"] = (
        dados_grafico["Hora Hora Wht (6to6)"] - 7
    ) % 24
    dados_grafico = dados_grafico.sort_values("Ordem Hora")
    dados_grafico["Hora"] = dados_grafico["Hora Hora Wht (6to6)"].map(
        lambda hora: f"{int(hora):02d}:00"
    )

    ordem_horas = dados_grafico["Hora"].tolist()

    figura = px.line(
        dados_grafico,
        x="Hora",
        y="Empacotado %",
        color="Prefixo",
        markers=True,
        title=f"Desempenho Hora a Hora — Máquina {maquina}",
        category_orders={"Hora": ordem_horas},
        color_discrete_sequence=[COR_LINHA_DESEMPENHO],
        labels={
            "Hora": "Hora",
            "Empacotado %": "Percentual empacotado",
            "Prefixo": "Prefixo",
        },
        hover_data={
            "Objetivo %": ":.2%",
            "Rejeição %": ":.2%",
            "Ordem Hora": False,
        },
    )

    figura.add_scatter(
        x=dados_grafico["Hora"],
        y=dados_grafico["Objetivo %"],
        mode="lines",
        name="Objetivo",
        line={"color": COR_LINHA_OBJETIVO, "dash": "dash", "width": 2},
        hovertemplate="Hora=%{x}<br>Objetivo=%{y:.2%}<extra></extra>",
    )

    figura.update_layout(
        hovermode="x unified",
    )
    figura.update_xaxes(type="category")
    figura.update_yaxes(tickformat=".0%", rangemode="tozero")

    return figura


def gerar_json_desempenho(
    maquinas_selecionadas: list[str],
    desempenho: pd.DataFrame | None = None,
    desempenho_hora_hora: pd.DataFrame | None = None,
) -> str:
    """
    Monta o JSON base por máquina com o desempenho diário, uma entrada por prefixo.
    As anotações são adicionadas depois, já interpretadas pela IA, por
    aplicar_anotacoes_interpretadas.

    Com o desempenho hora a hora, os prefixos saem na ordem em que rodaram no
    dia: em troca de máquina, primeiro o prefixo que saiu e depois o que entrou.
    """
    maquinas_sem_repeticao = list(dict.fromkeys(maquinas_selecionadas))
    desempenho_por_maquina = _desempenho_por_maquina_prefixo(desempenho)
    resultado = {}

    for maquina in maquinas_sem_repeticao:
        prefixos = desempenho_por_maquina.get(str(maquina), {})
        ordem = ordenar_prefixos_por_troca(
            desempenho_hora_hora,
            maquina,
            list(prefixos),
        )

        resultado[str(maquina)] = {
            "prefixos": {prefixo: dict(prefixos[prefixo]) for prefixo in ordem}
        }

    return json.dumps(resultado, ensure_ascii=False, indent=2, default=str)


def _registros_anotacoes(anotacoes: pd.DataFrame) -> list[dict]:
    colunas_para_remover = [
        coluna for coluna in ["Maquina", "Prefixo"] if coluna in anotacoes.columns
    ]

    return json.loads(
        anotacoes.drop(columns=colunas_para_remover).to_json(
            orient="records",
            date_format="iso",
            force_ascii=False,
        )
    )


def _desempenho_por_maquina_prefixo(
    desempenho: pd.DataFrame | None,
) -> dict[str, dict[str, dict]]:
    if desempenho is None or desempenho.empty:
        return {}

    colunas_desempenho = {
        "OP Vertech": "OP",
        "Objetivo %": "Objetivo %",
        "Empacotado %": "Empacotado %",
        "Rejeição %": "Rejeição %",
        "Emp - Rejeitado %": "Emp - Rejeitado %",
    }

    tabela = desempenho.reset_index()
    agrupado: dict[str, dict[str, dict]] = {}

    for linha in tabela.to_dict(orient="records"):
        maquina = str(linha.get("Maquina"))
        prefixo = str(linha.get("Prefixo"))

        agrupado.setdefault(maquina, {})[prefixo] = {
            nome_saida: _valor_json(linha.get(coluna))
            for coluna, nome_saida in colunas_desempenho.items()
            if coluna in tabela.columns
        }

    return agrupado


def _valor_json(valor):
    """Converte NaN/NaT em None para manter o JSON válido."""
    if valor is None or pd.isna(valor):
        return None
    if isinstance(valor, float):
        return round(valor, 2)
    return valor


def ops_do_relatorio(relatorio_json: str | dict) -> list[str]:
    """
    OPs presentes no JSON do relatório, sem repetição e na ordem em que
    aparecem — é por essa chave que os gráficos de desvios são anexados ao PDF.
    """
    dados = (
        json.loads(relatorio_json)
        if isinstance(relatorio_json, str)
        else relatorio_json
    )

    ops = []

    for conteudo in (dados or {}).values():
        prefixos = (conteudo or {}).get("prefixos") or {}

        for campos in prefixos.values():
            op = (campos or {}).get("OP")

            if op is not None and str(op).strip():
                ops.append(str(op).strip())

    return list(dict.fromkeys(ops))


def aplicar_anotacoes_interpretadas(
    anotacoes_json: str,
    interpretacoes: list[dict],
) -> str:
    """
    Substitui as anotações brutas do JSON pelas anotações interpretadas pela IA:
    a linha do tempo em 'anotacoes' e o resumo diário em 'observacoes'.

    O resumo em 'observacoes' é da máquina inteira, então o mesmo texto é
    repetido em todos os prefixos dela — inclusive nos que a IA não retornou,
    para nenhum item do relatório ficar sem resumo.

    Máquinas/prefixos que a IA não retornar mantêm a anotação bruta, para não
    perder informação silenciosamente.
    """
    dados = json.loads(anotacoes_json)
    resumos = _resumo_por_maquina(interpretacoes)

    for interpretacao in interpretacoes or []:
        maquina = str(interpretacao.get("maquina", "")).strip()
        prefixo = str(interpretacao.get("prefixo", "")).strip()
        linha_do_tempo = _linha_do_tempo(interpretacao.get("anotacoes"))
        observacoes = str(interpretacao.get("observacoes") or "").strip()

        if not maquina or not (linha_do_tempo or observacoes):
            continue

        dados_maquina = dados.setdefault(maquina, {"prefixos": {}})

        if prefixo:
            destino = dados_maquina.setdefault("prefixos", {}).setdefault(
                prefixo, {}
            )
        else:
            destino = dados_maquina

        destino["anotacoes"] = linha_do_tempo
        destino["observacoes"] = observacoes

    _aplicar_resumo_da_maquina(dados, resumos)

    return json.dumps(dados, ensure_ascii=False, indent=2, default=str)


def _resumo_por_maquina(interpretacoes: list[dict] | None) -> dict[str, str]:
    """
    Resumo diário de cada máquina: o primeiro texto não vazio que a IA devolveu
    para ela. A IA é instruída a repetir o mesmo resumo em todos os prefixos da
    máquina; este passo garante um único texto mesmo quando ela varia.
    """
    resumos: dict[str, str] = {}

    for interpretacao in interpretacoes or []:
        maquina = str(interpretacao.get("maquina", "")).strip()
        observacoes = str(interpretacao.get("observacoes") or "").strip()

        if maquina and observacoes and not resumos.get(maquina):
            resumos[maquina] = observacoes

    return resumos


def _aplicar_resumo_da_maquina(dados: dict, resumos: dict[str, str]) -> None:
    """Repete o resumo diário da máquina em todos os itens dela no relatório."""
    for maquina, conteudo in dados.items():
        resumo = resumos.get(str(maquina), "")

        if not resumo or not isinstance(conteudo, dict):
            continue

        prefixos = conteudo.get("prefixos")

        if isinstance(prefixos, dict) and prefixos:
            for campos in prefixos.values():
                if isinstance(campos, dict):
                    campos["observacoes"] = resumo
        else:
            conteudo["observacoes"] = resumo


def _linha_do_tempo(anotacoes) -> list[dict]:
    """
    Normaliza a linha do tempo devolvida pela IA, descartando entradas vazias e
    ordenando os eventos pelo dia Wheaton (06:00 às 05:59 do dia seguinte).
    """
    if not isinstance(anotacoes, list):
        return []

    eventos = []

    for evento in anotacoes:
        if not isinstance(evento, dict):
            continue

        descricao = str(evento.get("descricao") or "").strip()

        if not descricao:
            continue

        eventos.append(
            {
                "hora": _normalizar_hora(evento.get("hora")),
                "descricao": descricao,
            }
        )

    return sorted(eventos, key=_ordem_do_evento)


def _ordem_do_evento(evento: dict) -> tuple[int, int, int]:
    """Posição do evento no dia Wheaton; eventos sem hora reconhecida vão ao fim."""
    correspondencia = re.fullmatch(r"(\d{2}):(\d{2})", evento.get("hora", ""))

    if not correspondencia:
        return (1, 0, 0)

    hora = int(correspondencia.group(1))
    minuto = int(correspondencia.group(2))

    return (0, (hora - HORA_INICIO_DIA_WHEATON) % 24, minuto)


def _normalizar_hora(hora) -> str:
    """Deixa a hora no formato HH:MM; devolve o valor original quando não reconhece."""
    texto = str(hora or "").strip()

    if not texto:
        return ""

    correspondencia = re.fullmatch(r"(\d{1,2})\s*[:hH.]?\s*(\d{2})?", texto)

    if not correspondencia:
        return texto

    horas = int(correspondencia.group(1))
    minutos = int(correspondencia.group(2) or 0)

    if horas > 23 or minutos > 59:
        return texto

    return f"{horas:02d}:{minutos:02d}"


def gerar_markdown_resumo(anotacoes_json: str) -> str:
    """Monta o resumo em markdown a partir do JSON com as anotações interpretadas."""
    dados = json.loads(anotacoes_json)
    linhas: list[str] = []

    for maquina, conteudo in dados.items():
        linhas.append(f"### Máquina {maquina}")

        anotacao_maquina = conteudo.get("anotacoes")
        observacoes_maquina = conteudo.get("observacoes")

        for prefixo, campos in (conteudo.get("prefixos") or {}).items():
            linhas.append(f"**Prefixo {prefixo}** — {_linha_desempenho(campos)}")

            anotacao = campos.get("anotacoes", anotacao_maquina)
            linhas.append(_texto_anotacao(anotacao))
            linhas.append(
                _texto_observacoes(campos.get("observacoes", observacoes_maquina))
            )
            linhas.append("")

        if not conteudo.get("prefixos"):
            linhas.append(_texto_anotacao(anotacao_maquina))
            linhas.append(_texto_observacoes(observacoes_maquina))
            linhas.append("")

    return "\n".join(linhas).strip()


def _linha_desempenho(campos: dict) -> str:
    def formatar(chave: str) -> str:
        valor = campos.get(chave)
        return "—" if valor is None else f"{valor:.2f}%".replace(".", ",")

    op = campos.get("OP") or "sem OP"

    return (
        f"OP {op} | Objetivo {formatar('Objetivo %')} | "
        f"Empacotado {formatar('Empacotado %')} | "
        f"Rejeição {formatar('Rejeição %')} | "
        f"Emp - Rejeitado {formatar('Emp - Rejeitado %')}"
    )


def _texto_anotacao(anotacao) -> str:
    if isinstance(anotacao, str):
        return anotacao

    if isinstance(anotacao, list) and anotacao:
        return "\n".join(_linha_evento(registro) for registro in anotacao)

    return "_Sem anotações._"


def _linha_evento(registro) -> str:
    if not isinstance(registro, dict):
        return f"- {registro}"

    hora = _hora_exibicao(registro.get("hora"))
    descricao = registro.get("descricao")

    if descricao is None:
        return f"- {registro}"

    return f"- **{hora}** — {descricao}" if hora else f"- {descricao}"


def _hora_exibicao(hora) -> str:
    """Formata 'HH:MM' como '04h45', o formato usado no relatório."""
    texto = str(hora or "").strip()
    correspondencia = re.fullmatch(r"(\d{2}):(\d{2})", texto)

    return f"{correspondencia.group(1)}h{correspondencia.group(2)}" if correspondencia else texto


def _texto_observacoes(observacoes) -> str:
    texto = str(observacoes or "").strip()

    return f"\n_Observações:_ {texto}" if texto else ""
