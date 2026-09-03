import asyncio

import pandas as pd
import streamlit as st

from utils.data_processor import (
    aplicar_anotacoes_interpretadas,
    gerar_grafico_desempenho_hora_hora,
    gerar_json_anotacoes_por_maquina,
    gerar_json_desempenho,
    gerar_markdown_resumo,
    process_excel_producao,
)
from utils.openai_integration import get_anotacoes_interpretadas
from utils.pdf_processor import gerar_pdf_resumo_anotacoes


st.set_page_config(
    page_title="Relatório da Produção",
    layout="wide",
)

st.title("Relatório Diário da Produção")

with st.form("form_arquivos"):
    coluna_producao, coluna_notas = st.columns(2)

    with coluna_producao:
        excel_producao = st.file_uploader(
            "Upload do excel de produção",
            type=["xlsx"],
            key="file_uploader_producao",
            accept_multiple_files=False,
        )

    with coluna_notas:
        excel_notas = st.file_uploader(
            "Upload do bloco de notas",
            type=["xlsx"],
            key="file_uploader_notas",
            accept_multiple_files=False,
        )

    iniciar_automacao = st.form_submit_button(
        "Iniciar Análise",
        type="primary",
        width="stretch",
    )

if iniciar_automacao:
    if excel_producao is None or excel_notas is None:
        st.warning("Envie os dois arquivos para iniciar a automação.")
    else:
        try:
            desempenho, desempenho_hora_hora = process_excel_producao(
                excel_producao
            )

            df_notas = pd.read_excel(excel_notas)
            df_notas = df_notas.drop(
                columns=["Unnamed: 1"],
                errors="ignore",
            )
            df_notas.columns = df_notas.iloc[1]
            df_notas = df_notas.iloc[2:].reset_index(drop=True)
            df_notas.columns.name = None
        except Exception as erro:
            st.error(f"Não foi possível processar os arquivos: {erro}")
        else:
            st.session_state["desempenho_producao"] = desempenho.copy()
            st.session_state["desempenho_hora_hora"] = (
                desempenho_hora_hora.copy()
            )
            st.session_state["df_notas"] = df_notas.copy()

            st.session_state.pop("anotacoes_resumidas", None)
            st.session_state.pop("json_interpretado", None)
            st.session_state.pop("resumo_anotacoes", None)
            st.session_state.pop("maquinas_resumidas", None)
            st.session_state.pop("maquinas_relatorio", None)
            st.session_state.pop("maquina_hora_hora", None)
            st.session_state.pop("prefixo_hora_hora", None)

desempenho = st.session_state.get("desempenho_producao")
desempenho_hora_hora = st.session_state.get("desempenho_hora_hora")
df_notas = st.session_state.get("df_notas")

arquivos_processados = (
    desempenho is not None
    and desempenho_hora_hora is not None
    and df_notas is not None
)

if arquivos_processados:
    st.subheader("Resumo de Desempenho Diário")

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
                desempenho_exibicao["Emp - Rejeitado %"]
                < desempenho_exibicao["Objetivo %"]
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
            desempenho_exibicao.style.apply(
                lambda coluna: [
                    estilo_vermelho if abaixo else estilo_verde
                    for abaixo in abaixo_objetivo
                ],
                subset=["Maquina", "Empacotado %", "Emp - Rejeitado %"],
                axis=0,
            )
            .format(
                {
                    "Objetivo %": "{:.2f}",
                    "Empacotado %": "{:.2f}",
                    "Rejeição %": "{:.2f}",
                    "Emp - Rejeitado %": "{:.2f}",
                }
            )
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
            st.warning(
                "Não há dados hora a hora disponíveis para visualização."
            )
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

            st.subheader("Anotações do dia")
            # st.badge(f"Máquina {maquina_selecionada}", color="blue")

            df_notas_filtrado = df_notas.loc[
                df_notas["Maquina"] == maquina_selecionada
            ]

            dados, resumo = st.tabs(["Dados", "Relatório"])

            with dados:
                st.dataframe(df_notas_filtrado, use_container_width=True)

            with resumo:
                st.subheader("Relatório Diário")

                maquinas_disponiveis_relatorio = (
                    desempenho.reset_index()["Maquina"]
                    .dropna()
                    .drop_duplicates()
                    .tolist()
                )

                with st.expander("Configurar relatório diário"):
                    maquinas_para_relatorio = st.multiselect(
                        "Selecione as máquinas para a geração do relatório",
                        options=maquinas_disponiveis_relatorio,
                        key="maquinas_relatorio",
                        placeholder="Selecione uma ou mais máquinas",
                    )

                    gerar_relatorio = st.button(
                        "Gerar relatório",
                        type="primary",
                        disabled=not maquinas_para_relatorio,
                    )

                if maquinas_para_relatorio:
                    anotacoes_json = gerar_json_anotacoes_por_maquina(
                        df_notas,
                        maquinas_para_relatorio,
                    )
                    desempenho_json = gerar_json_desempenho(
                        maquinas_para_relatorio,
                        desempenho,
                    )
                    chave_resumo = f"{anotacoes_json}{desempenho_json}"

                    if gerar_relatorio:
                        try:
                            with st.spinner(
                                "Interpretando anotações com IA...",
                                show_time=True,
                            ):
                                interpretacoes = asyncio.run(
                                    get_anotacoes_interpretadas(anotacoes_json)
                                )
                                json_interpretado = (
                                    aplicar_anotacoes_interpretadas(
                                        desempenho_json,
                                        interpretacoes,
                                    )
                                )
                        except Exception as erro:
                            st.error(
                                f"Não foi possível gerar o relatório: {erro}"
                            )
                        else:
                            st.session_state["anotacoes_resumidas"] = chave_resumo
                            st.session_state["json_interpretado"] = (
                                json_interpretado
                            )
                            st.session_state["resumo_anotacoes"] = (
                                gerar_markdown_resumo(json_interpretado)
                            )
                            st.session_state["maquinas_resumidas"] = (
                                maquinas_para_relatorio.copy()
                            )

                    resumo_ia = st.session_state.get("resumo_anotacoes")
                    json_interpretado = st.session_state.get(
                        "json_interpretado"
                    )
                    resumo_corresponde_as_anotacoes = (
                        st.session_state.get("anotacoes_resumidas")
                        == chave_resumo
                    )

                    if resumo_corresponde_as_anotacoes and resumo_ia:
                        st.caption("Máquinas incluídas no relatório:")

                        with st.container(horizontal=True):
                            for maquina in maquinas_para_relatorio:
                                st.badge(maquina, color="gray")

                        pdf_relatorio = gerar_pdf_resumo_anotacoes(
                            json_interpretado
                        )

                        with st.bottom:
                            st.download_button(
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


                    ### DEBUG
                    # if resumo_corresponde_as_anotacoes and json_interpretado:
                    #     with st.expander(
                    #         "JSON com as anotações interpretadas pela IA"
                    #     ):
                    #         st.json(json_interpretado, expanded=False)
                    # else:
                    #     with st.expander(
                    #         "Anotações que serão enviadas para a IA (JSON)"
                    #     ):
                    #         st.json(anotacoes_json, expanded=False)

elif not iniciar_automacao:
    st.info(
        "Envie os arquivos de produção e de notas para iniciar a automação."
    )
