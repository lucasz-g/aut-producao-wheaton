import asyncio

import streamlit as st
import pandas as pd
from utils.data_processor import (
    gerar_grafico_desempenho_hora_hora,
    gerar_json_anotacoes_por_maquina,
    process_excel_producao,
)
from utils.openai_integration import get_openai_response
from utils.pdf_processor import gerar_pdf_resumo_anotacoes

st.set_page_config(
    page_title="Relatório da Produção",
    layout="wide",
)

st.title("Relatório Diário da Produção")

producao, notas = st.tabs(["Produção", "Notas"])

with producao:
    st.subheader("Resumo de Desempenho Diário")
    excel_producao = st.file_uploader("Upload do excel de produção", type=["xlsx"], key="file_uploader_producao", accept_multiple_files=False)
    if excel_producao:
        # st.success("Arquivo carregado com sucesso!")
        desempenho, desempenho_hora_hora = process_excel_producao(excel_producao)
        st.session_state["desempenho_producao"] = desempenho.copy()
        st.session_state["desempenho_hora_hora"] = desempenho_hora_hora.copy()

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
                    (desempenho_exibicao["Emp - Rejeitado %"]
                    < desempenho_exibicao["Objetivo %"])
                ].copy()
            elif visualizacao == "No objetivo ou acima":
                desempenho_exibicao = desempenho_exibicao.loc[
                    desempenho_exibicao["Emp - Rejeitado %"]
                    >= desempenho_exibicao["Objetivo %"]
                ].copy()

            abaixo_objetivo = (
                desempenho_exibicao["Emp - Rejeitado %"]
                < desempenho_exibicao["Objetivo %"]
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
                    subset=["Maquina", "Empacotado %", "Emp - Rejeitado %"],
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
    else:
        st.session_state.pop("desempenho_producao", None)
        st.session_state.pop("desempenho_hora_hora", None)

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
            resumir_anotacoes = st.button(
                "Gerar resumo",
                disabled=not maquinas_selecionadas,
            )

            if not maquinas_selecionadas:
                st.info(
                    "Selecione pelo menos uma máquina para gerar o resumo das anotações."
                )
            else:
                anotacoes_json = gerar_json_anotacoes_por_maquina(
                    df_notas,
                    maquinas_selecionadas,
                )

                if resumir_anotacoes:
                    try:
                        with st.spinner(
                            "Resumindo anotações com IA...",
                            show_time=True,
                        ):
                            resumo_ia = asyncio.run(
                                get_openai_response(anotacoes_json)
                            )
                    except Exception as erro:
                        st.error(f"Não foi possível gerar o resumo: {erro}")
                    else:
                        st.session_state["anotacoes_resumidas"] = anotacoes_json
                        st.session_state["resumo_anotacoes"] = resumo_ia
                        st.session_state["maquinas_resumidas"] = list(
                            maquinas_selecionadas
                        )

                resumo_ia = st.session_state.get("resumo_anotacoes")
                resumo_corresponde_as_anotacoes = (
                    st.session_state.get("anotacoes_resumidas") == anotacoes_json
                )

                if resumo_corresponde_as_anotacoes and resumo_ia:
                    st.caption("Máquinas selecionadas:")

                    with st.container(horizontal=True):
                        for maquina in maquinas_selecionadas:
                            st.badge(maquina, color="gray")

                    with st.container(border=True, width="content"):
                        st.markdown(resumo_ia)

                    pdf_relatorio = gerar_pdf_resumo_anotacoes(resumo_ia)

                    with st.bottom:
                        baixar_relatorio_diario = st.download_button(
                            "Baixar relatório diário",
                            data=pdf_relatorio,
                            file_name="relatorio_diario.pdf",
                            mime="application/pdf",
                            type="primary",
                            width="stretch",
                            on_click="ignore",
                        )
                elif resumo_corresponde_as_anotacoes:
                    st.warning("A IA não retornou um resumo.")
