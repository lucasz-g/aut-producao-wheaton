import json
import re

import pandas as pd
import plotly.express as px


def process_excel_producao(excel_file):
    df = pd.read_excel(excel_file)
    df = adjust_columns(df)
    df = adjust_float(df)

    desempenho_empacotamento_diario = get_desempenho_diario(df)
    desempenho_hora_hora = get_desempenho_hora_hora(df)

    return desempenho_empacotamento_diario, desempenho_hora_hora


# def get_maquinas_abaixo_objetivo(desempenho: pd.DataFrame) -> list[str]:
#     desempenho_exibicao = desempenho.reset_index()

#     maquinas = desempenho_exibicao.loc[
#         desempenho_exibicao["Emp - Rejeitado %"]
#         < desempenho_exibicao["Objetivo %"],
#         "Maquina",
#     ]

#     return maquinas.dropna().drop_duplicates().tolist()


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
    """
    if "Maquina" not in df_notas.columns:
        raise ValueError("A coluna 'Maquina' não foi encontrada nas anotações.")

    notas_tem_prefixo = "Prefixo" in df_notas.columns
    maquinas_sem_repeticao = list(dict.fromkeys(maquinas_selecionadas))
    anotacoes_por_maquina = {}

    for maquina in maquinas_sem_repeticao:
        anotacoes_maquina = df_notas.loc[df_notas["Maquina"] == maquina]

        if notas_tem_prefixo:
            anotacoes_por_maquina[str(maquina)] = {
                str(prefixo): _registros_anotacoes(anotacoes_prefixo)
                for prefixo, anotacoes_prefixo in anotacoes_maquina.groupby(
                    anotacoes_maquina["Prefixo"].astype("string").fillna("Sem prefixo")
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
        line={"color": "#ff4b4b", "dash": "dash", "width": 2},
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
) -> str:
    """
    Monta o JSON base por máquina com o desempenho diário, uma entrada por prefixo.
    As anotações são adicionadas depois, já interpretadas pela IA, por
    aplicar_anotacoes_interpretadas.
    """
    maquinas_sem_repeticao = list(dict.fromkeys(maquinas_selecionadas))
    desempenho_por_maquina = _desempenho_por_maquina_prefixo(desempenho)

    resultado = {
        str(maquina): {
            "prefixos": {
                prefixo: dict(campos)
                for prefixo, campos in desempenho_por_maquina.get(
                    str(maquina), {}
                ).items()
            }
        }
        for maquina in maquinas_sem_repeticao
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


def aplicar_anotacoes_interpretadas(
    anotacoes_json: str,
    interpretacoes: list[dict],
) -> str:
    """
    Substitui as anotações brutas do JSON pelas anotações interpretadas pela IA:
    a linha do tempo em 'anotacoes' e o texto sem hora em 'observacoes'.

    Máquinas/prefixos que a IA não retornar mantêm a anotação bruta, para não
    perder informação silenciosamente.
    """
    dados = json.loads(anotacoes_json)

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

    return json.dumps(dados, ensure_ascii=False, indent=2, default=str)


def _linha_do_tempo(anotacoes) -> list[dict]:
    """Normaliza a linha do tempo devolvida pela IA, descartando entradas vazias."""
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

    return eventos


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
