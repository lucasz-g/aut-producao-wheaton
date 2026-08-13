import asyncio

import streamlit as st
import pandas as pd
from utils.data_processor import (
    gerar_grafico_desempenho_hora_hora,
    gerar_json_anotacoes_por_maquina,
    process_excel_producao,
)
from utils.openai_integration import get_openai_response

st.set_page_config(
    page_title="Resumo da Produção",
    layout="wide",
)

st.title("Resumo Diário da Produção")

producao, notas, relatorio = st.tabs(["Produção", "Notas", "Relatório"])

with producao:
    st.subheader("Resumo de Desempenho Diário")
    excel_producao = st.file_uploader("Upload do excel de produção", type=["xlsx"], key="file_uploader_producao", accept_multiple_files=False)
    if excel_producao:
        # st.success("Arquivo carregado com sucesso!")
        desempenho, desempenho_hora_hora = process_excel_producao(excel_producao)

        diario, hora_hora = st.tabs(["Diário", "Hora a Hora"])

        with diario:
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

        with hora_hora:
            st.subheader("Desempenho Hora a Hora")

            maquinas_disponiveis = (
                desempenho_hora_hora["Maquina"].dropna().unique().tolist()
            )

            if not maquinas_disponiveis:
                st.warning("Não há dados hora a hora disponíveis para visualização.")
            else:
                maquina_selecionada = st.selectbox(
                    "Selecione a máquina",
                    options=maquinas_disponiveis,
                    key="maquina_hora_hora",
                )

                prefixos_disponiveis = (
                    desempenho_hora_hora.loc[
                        desempenho_hora_hora["Maquina"] == maquina_selecionada,
                        "Prefixo",
                    ]
                    .dropna()
                    .unique()
                    .tolist()
                )

                if len(prefixos_disponiveis) > 1:
                    prefixo_selecionado = st.selectbox(
                        "Selecione o prefixo",
                        options=prefixos_disponiveis,
                        key="prefixo_hora_hora",
                    )
                else:
                    prefixo_selecionado = prefixos_disponiveis[0]
                    st.caption(f"Prefixo: {prefixo_selecionado}")

                figura = gerar_grafico_desempenho_hora_hora(
                    desempenho_hora_hora,
                    maquina_selecionada,
                    prefixo_selecionado,
                )

                st.plotly_chart(figura, use_container_width=True)

with notas:
    st.subheader("Anotações do dia")
    excel_notas = st.file_uploader("Upload do bloco de notas", type=["xlsx"], key="file_uploader_notas")


    if excel_notas:
        df_notas = pd.read_excel(excel_notas)
        df_notas = df_notas.drop(columns=['Unnamed: 1'])

        df_notas.columns = df_notas.iloc[1]
        df_notas = df_notas.iloc[2:].reset_index(drop=True)
        df_notas.columns.name = None

        maquinas_selecionadas = st.multiselect(
            "Selecione a máquina para visualizar as anotações",
            options=df_notas["Maquina"].dropna().unique(),
            key="selectbox_maquina",
            placeholder="Selecione a máquina",
        )

        df_notas_filtrado = df_notas[
            df_notas["Maquina"].isin(maquinas_selecionadas)
        ]

        dados, resumo = st.tabs(["Dados", "Resumo"])
        with dados:
            if maquinas_selecionadas:
                st.dataframe(df_notas_filtrado, use_container_width=True)
            else:
                st.dataframe(df_notas, use_container_width=True)
        with resumo:
            st.subheader("Resumo das anotações")
            resumo_notas = st.button(
                label="Resumir Anotações",
                disabled=not maquinas_selecionadas,
            )

            if not maquinas_selecionadas:
                st.info(
                    "Selecione pelo menos uma máquina para gerar o resumo das anotações."
                )

            if resumo_notas:
                st.caption("Máquinas selecionadas:")

                with st.container(horizontal=True):
                    for maquina in maquinas_selecionadas:
                        st.badge(maquina, color="gray")

                anotacoes_json = gerar_json_anotacoes_por_maquina(
                    df_notas,
                    maquinas_selecionadas,
                )

                try:
                    with st.spinner("Resumindo anotações com IA...", show_time=True):
                        resumo_ia = asyncio.run(
                            get_openai_response(anotacoes_json)
                        )
                except Exception as erro:
                    st.error(f"Não foi possível gerar o resumo: {erro}")
                else:
                    if resumo_ia:
                        with st.container(border=True, width="content"):
                            st.markdown(resumo_ia)
                    else:
                        st.warning("A IA não retornou um resumo.")

with relatorio:
    st.subheader("Relatório Geral")
    with st.container(border=True, width="content"):
        st.write("Faça o Download do Relatório de Desempenho Diário")

        gerar_relatorio = st.button(
            label="Download do Relatório",
        )

    if gerar_relatorio:
        st.info("A funcionalidade de download do relatório ainda não foi implementada.")
