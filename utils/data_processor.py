import json

import pandas as pd
import plotly.express as px


def process_excel_producao(excel_file):
    df = pd.read_excel(excel_file)
    df = adjust_columns(df)
    df = adjust_float(df)

    desempenho_empacotamento_diario = get_desempenho_diario(df)
    desempenho_hora_hora = get_desempenho_hora_hora(df)

    return desempenho_empacotamento_diario, desempenho_hora_hora


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
    if "Maquina" not in df_notas.columns:
        raise ValueError("A coluna 'Maquina' não foi encontrada nas anotações.")

    maquinas_sem_repeticao = list(dict.fromkeys(maquinas_selecionadas))
    anotacoes_por_maquina = {}

    for maquina in maquinas_sem_repeticao:
        anotacoes_maquina = (
            df_notas.loc[df_notas["Maquina"] == maquina]
            .drop(columns=["Maquina"])
        )

        anotacoes_por_maquina[str(maquina)] = json.loads(
            anotacoes_maquina.to_json(
                orient="records",
                date_format="iso",
                force_ascii=False,
            )
        )

    return json.dumps(
        anotacoes_por_maquina,
        ensure_ascii=False,
        indent=2,
    )


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
