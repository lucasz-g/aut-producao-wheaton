"""Exportação dos gráficos de desempenho como imagem, para anexar no PDF."""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils.data_processor import gerar_grafico_desempenho_hora_hora

LARGURA_PNG = 1000
ALTURA_PNG = 420
ALTURA_PNG_DESVIOS = 520
ESCALA_PNG = 2


def exportar_figura_png(
    figura,
    largura: int = LARGURA_PNG,
    altura: int = ALTURA_PNG,
    escala: int = ESCALA_PNG,
) -> bytes:
    """Converte uma figura Plotly em PNG (requer o kaleido instalado)."""
    return _preparar_para_impressao(figura).to_image(
        format="png",
        width=largura,
        height=altura,
        scale=escala,
    )


def gerar_graficos_por_prefixo(
    desempenho_hora_hora: pd.DataFrame | None,
    maquinas: list[str],
) -> dict[str, dict[str, bytes]]:
    """
    PNG do gráfico hora a hora de cada máquina/prefixo informado, na estrutura
    {"14": {"LB -0478-N1": b"...png"}} — as mesmas chaves usadas no JSON do
    relatório, para o PDF só precisar consultar por máquina e prefixo.

    Máquinas/prefixos sem dados hora a hora (ou cuja exportação falhar) são
    apenas omitidos: o relatório continua sendo gerado sem o gráfico.
    """
    if desempenho_hora_hora is None or desempenho_hora_hora.empty:
        return {}

    graficos: dict[str, dict[str, bytes]] = {}

    for maquina in dict.fromkeys(maquinas):
        for prefixo in _prefixos_da_maquina(desempenho_hora_hora, maquina):
            try:
                figura = gerar_grafico_desempenho_hora_hora(
                    desempenho_hora_hora,
                    maquina,
                    prefixo,
                )
                imagem = exportar_figura_png(figura)
            except Exception:
                continue

            graficos.setdefault(str(maquina), {})[str(prefixo)] = imagem

    return graficos


def _preparar_para_impressao(figura) -> go.Figure:
    """
    Fundo branco, sem título (o PDF já traz o seu) e legenda no rodapé, sem
    alterar a figura exibida na tela.
    """
    copia = go.Figure(figura)

    copia.update_layout(
        template="plotly_white",
        title=None,
        margin={"l": 60, "r": 30, "t": 20, "b": 70},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": -0.32,
            "xanchor": "center",
            "x": 0.5,
        },
    )

    return copia


def _prefixos_da_maquina(desempenho_hora_hora: pd.DataFrame, maquina) -> list:
    return (
        desempenho_hora_hora.loc[
            desempenho_hora_hora["Maquina"] == maquina,
            "Prefixo",
        ]
        .dropna()
        .drop_duplicates()
        .tolist()
    )


def gerar_grafico_comparativo_aq_af(
    df_diario: pd.DataFrame | None,
) -> dict[str, go.Figure]:
    """
    Compara o Top 5 de desvios das localizações AQ e AF de cada OP, na
    estrutura {"198618": figura} — uma figura por OP Vertech que tenha dados
    nas duas localizações. Quem chama decide como exibir (st.plotly_chart na
    tela ou exportar_figura_png no PDF).
    """
    if df_diario is None or df_diario.empty:
        return {}

    # Cria a base utilizada na comparação entre AQ e AF
    base_aq_af = df_diario.copy()

    # Padroniza as colunas de texto
    for coluna in [
        "OP Vertech",
        "Desvio sigla",
        "Localizacao",
    ]:
        base_aq_af[coluna] = (
            base_aq_af[coluna]
            .astype("string")
            .str.strip()
        )
    
    base_aq_af["Localizacao"] = (
        base_aq_af["Localizacao"]
        .str.upper()
    )
    
    # Garante que as quantidades sejam numéricas
    for coluna in [
        "Qtd Amostra (corrigido)",
        "Qtd Defeito",
    ]:
        base_aq_af[coluna] = pd.to_numeric(
            base_aq_af[coluna],
            errors="coerce",
        )
    
    # Mantém apenas AQ e AF
    base_aq_af = (
        base_aq_af[
            base_aq_af["Localizacao"].isin(
                ["AQ", "AF"]
            )
        ]
        .dropna(
            subset=[
                "OP Vertech",
                "Desvio sigla",
            ]
        )
        .copy()
    )
    
    # Consolida os valores por OP, desvio e localização
    resumo_aq_af = (
        base_aq_af
        .groupby(
            [
                "OP Vertech",
                "Desvio sigla",
                "Localizacao",
            ],
            as_index=False,
            observed=True,
        )
        .agg(
            Qtd_Amostra=(
                "Qtd Amostra (corrigido)",
                "sum",
            ),
            Qtd_Defeito=(
                "Qtd Defeito",
                "sum",
            ),
        )
    )
    
    # Calcula o percentual consolidado de defeitos
    resumo_aq_af["Percentual_Defeito"] = (
        resumo_aq_af["Qtd_Defeito"]
        / resumo_aq_af["Qtd_Amostra"].where(
            resumo_aq_af["Qtd_Amostra"].gt(0)
        )
    )
    
    # Seleciona o Top 5 de cada localização separadamente
    top5_aq_af = (
        resumo_aq_af
        .query("Localizacao in ['AQ', 'AF']")
        .dropna(subset=["Percentual_Defeito"])
        .sort_values(
            [
                "OP Vertech",
                "Localizacao",
                "Percentual_Defeito",
                "Desvio sigla",
            ],
            ascending=[True, True, False, True],
        )
        .groupby(
            ["OP Vertech", "Localizacao"],
            sort=False,
            observed=True,
        )
        .head(5)
    )
    
    # Mantém somente OPs que possuem dados nas duas localizações
    ops_com_aq_e_af = (
        top5_aq_af
        .groupby(
            "OP Vertech",
            observed=True,
        )["Localizacao"]
        .nunique()
        .loc[lambda valores: valores.eq(2)]
        .index
    )
    
    cores = {
        "AQ": "#D62728",
        "AF": "#1F77B4",
    }

    graficos: dict[str, go.Figure] = {}

    for op_vertech in ops_com_aq_e_af:
        dados_op = top5_aq_af[
            top5_aq_af["OP Vertech"].eq(op_vertech)
        ]
    
        aq = (
            dados_op[
                dados_op["Localizacao"].eq("AQ")
            ]
            .sort_values(
                "Percentual_Defeito",
                ascending=False,
            )
            .reset_index(drop=True)
        )
    
        af = (
            dados_op[
                dados_op["Localizacao"].eq("AF")
            ]
            .sort_values(
                "Percentual_Defeito",
                ascending=False,
            )
            .reset_index(drop=True)
        )
    
        # Posições representam o ranking em cada localização
        posicoes_aq = list(range(len(aq)))
        posicoes_af = list(range(len(af)))
        quantidade_linhas = max(len(aq), len(af))
    
        # Mantém os dois lados com a mesma escala
        maior_percentual = max(
            aq["Percentual_Defeito"].max(),
            af["Percentual_Defeito"].max(),
        )
    
        limite_eixo = (
            maior_percentual * 1.25
            if maior_percentual > 0
            else 0.01
        )
    
        fig = make_subplots(
            rows=1,
            cols=2,
            horizontal_spacing=0.10,
            subplot_titles=(
                "<b>Localização AQ</b>",
                "<b>Localização AF</b>",
            ),
        )
    
        # Top 5 da AQ — barras voltadas para a esquerda
        fig.add_trace(
            go.Bar(
                x=aq["Percentual_Defeito"],
                y=posicoes_aq,
                orientation="h",
                marker_color=cores["AQ"],
                text=aq["Percentual_Defeito"],
                texttemplate="%{text:.2%}",
                textposition="outside",
                cliponaxis=False,
                customdata=aq[
                    ["Qtd_Defeito"]
                ].to_numpy(),
                hovertemplate=(
                    "<b>Desvio:</b> %{y}<br>"
                    "<b>Localização:</b> AQ<br>"
                    "<b>Percentual:</b> %{x:.2%}<br>"
                    "<b>Qtd. defeitos:</b> %{customdata[0]:,.0f}"
                    "<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )
    
        # Top 5 da AF — barras voltadas para a direita
        fig.add_trace(
            go.Bar(
                x=af["Percentual_Defeito"],
                y=posicoes_af,
                orientation="h",
                marker_color=cores["AF"],
                text=af["Percentual_Defeito"],
                texttemplate="%{text:.2%}",
                textposition="outside",
                cliponaxis=False,
                customdata=af[
                    ["Qtd_Defeito"]
                ].to_numpy(),
                hovertemplate=(
                    "<b>Desvio:</b> %{y}<br>"
                    "<b>Localização:</b> AF<br>"
                    "<b>Percentual:</b> %{x:.2%}<br>"
                    "<b>Qtd. defeitos:</b> %{customdata[0]:,.0f}"
                    "<extra></extra>"
                ),
            ),
            row=1,
            col=2,
        )
    
        # Eixo da AQ invertido: zero fica próximo ao centro
        fig.update_xaxes(
            title_text="Percentual AQ",
            tickformat=".1%",
            range=[limite_eixo, 0],
            row=1,
            col=1,
        )
    
        # Eixo da AF: zero fica próximo ao centro
        fig.update_xaxes(
            title_text="Percentual AF",
            tickformat=".1%",
            range=[0, limite_eixo],
            row=1,
            col=2,
        )
    
        # Desvios próprios da AQ
        fig.update_yaxes(
            title_text="Top 5 desvios da AQ",
            tickmode="array",
            tickvals=posicoes_aq,
            ticktext=aq["Desvio sigla"],
            range=[
                quantidade_linhas - 0.5,
                -0.5,
            ],
            row=1,
            col=1,
        )
    
        # Desvios próprios da AF, exibidos à direita
        fig.update_yaxes(
            title_text="Top 5 desvios da AF",
            tickmode="array",
            tickvals=posicoes_af,
            ticktext=af["Desvio sigla"],
            range=[
                quantidade_linhas - 0.5,
                -0.5,
            ],
            side="right",
            row=1,
            col=2,
        )
    
        fig.update_layout(
            title=dict(
                text=(
                    "Top 5 desvios detectados em AQ e AF"
                    f"<br>OP Vertech: {op_vertech}"
                ),
                x=0.5,
            ),
            template="plotly_white",
            width=950,
            height=480,
            showlegend=False,
            bargap=0.20,
            margin=dict(
                l=100,
                r=100,
                t=110,
                b=65,
            ),
        )

        graficos[str(op_vertech)] = fig

    return graficos

def gerar_graficos_desvios_por_op(
    graficos_aq_af: dict[str, go.Figure] | None,
    ops: list[str],
) -> dict[str, bytes]:
    """
    PNG do comparativo AQ x AF de cada OP informada, na estrutura
    {"198594": b"...png"} — a mesma chave "OP" usada no JSON do relatório, para
    o PDF só precisar consultar pela OP do prefixo.

    OPs sem gráfico (ou cuja exportação falhar) são apenas omitidas: o
    relatório continua sendo gerado sem a imagem.
    """
    if not graficos_aq_af:
        return {}

    imagens: dict[str, bytes] = {}

    for op in dict.fromkeys(str(op).strip() for op in ops if op is not None):
        figura = graficos_aq_af.get(op)

        if figura is None:
            continue

        try:
            imagens[op] = _preparar_desvios_para_impressao(figura).to_image(
                format="png",
                width=LARGURA_PNG,
                height=ALTURA_PNG_DESVIOS,
                scale=ESCALA_PNG,
            )
        except Exception:
            continue

    return imagens


def _preparar_desvios_para_impressao(figura) -> go.Figure:
    """
    Fundo branco e sem o título da OP (o PDF já traz o seu), mantendo espaço no
    topo para os títulos dos dois subplots.
    """
    copia = go.Figure(figura)

    copia.update_layout(
        template="plotly_white",
        title=None,
        width=None,
        height=None,
        margin={"l": 90, "r": 90, "t": 45, "b": 60},
    )

    return copia
