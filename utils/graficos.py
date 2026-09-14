"""Exportação dos gráficos de desempenho como imagem, para anexar no PDF."""

import pandas as pd
import plotly.graph_objects as go

from utils.data_processor import gerar_grafico_desempenho_hora_hora

LARGURA_PNG = 1000
ALTURA_PNG = 420
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
