import pandas as pd
import numpy as np

def process_excel_producao (excel_file: pd.DataFrame):
    df = pd.read_excel(excel_file)
    df = adjust_columns(df)
    df = adjust_float(df)

    desempenho_empacotamento_diario = desempenho_diario(df)

    return desempenho_empacotamento_diario


def adjust_columns(df : pd.DataFrame):
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


def desempenho_diario(df: pd.DataFrame):
    desempenho_empacotamento_diario = df.groupby(["Maquina", "Prefixo"]).agg({'Objetivo %': 'min', 'Empacotado %': 'mean', 'Rejeição %': 'mean'})

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
