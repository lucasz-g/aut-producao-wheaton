import streamlit as st
import pandas as pd
from utils.data_processor import process_excel_producao

st.set_page_config(
    page_title="Resumo da Produção",
    layout="wide",
)

st.title("Resumo Diário da Produção")

producao, notas, resumo_geral = st.tabs(["Produção", "Notas", "Resumo Geral"])

with producao:
    st.subheader("Resumo de Desempenho Diário")
    excel_producao = st.file_uploader("Upload do excel de produção", type=["xlsx"], key="file_uploader_producao", accept_multiple_files=False)
    if excel_producao:
        # st.success("Arquivo carregado com sucesso!")
        desempenho = process_excel_producao(excel_producao)

        desempenho_exibicao = desempenho.reset_index()

        visualizacao = st.pills(
            "Visualização",
            ["Geral", "Abaixo do objetivo", "No objetivo ou acima"],
            default="Geral",
            selection_mode="single",
        )

        if visualizacao == "Abaixo do objetivo":
            desempenho_exibicao = desempenho_exibicao.loc[
                desempenho_exibicao["Empacotado %"]
                < desempenho_exibicao["Objetivo %"]
            ].copy()
        elif visualizacao == "No objetivo ou acima":
            desempenho_exibicao = desempenho_exibicao.loc[
                desempenho_exibicao["Empacotado %"]
                >= desempenho_exibicao["Objetivo %"]
            ].copy()

        abaixo_objetivo = (
            desempenho_exibicao["Empacotado %"] < desempenho_exibicao["Objetivo %"]
        )

        estilo_vermelho = "color: #ff4b4b;"
        estilo_verde = "color: #4CBF70;"

        tabela_estilizada = (
            desempenho_exibicao.style
            .apply(
                lambda coluna: [
                    estilo_vermelho if abaixo else estilo_verde
                    for abaixo in abaixo_objetivo
                ],
                subset=["Maquina", "Empacotado %"],
                axis=0,
            )
            .format({
                "Objetivo %": "{:.2f}",
                "Empacotado %": "{:.2f}",
                "Rejeição %": "{:.2f}",
                "Emp - Rejeitado %": "{:.2f}",
            })
            .hide(axis="index")
        )

        st.dataframe(
            tabela_estilizada,
            use_container_width=True,
        )



with notas:
    st.subheader("Anotações do dia")
    excel_notas = st.file_uploader("Upload do bloco de notas", type=["xlsx"], key="file_uploader_notas")
    if excel_notas:
        df_notas = pd.read_excel(excel_notas)
        st.dataframe(df_notas, use_container_width=True)


with resumo_geral:
    st.subheader("Resumo Geral")
    st.write("Faça o Download do Relatório de Desempenho Diário")