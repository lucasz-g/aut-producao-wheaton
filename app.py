import asyncio

import streamlit as st

from utils.data_processor import (
    aplicar_anotacoes_interpretadas,
    gerar_grafico_desempenho_hora_hora,
    gerar_json_anotacoes_por_maquina,
    gerar_json_desempenho,
    gerar_markdown_resumo,
    get_maquinas_abaixo_objetivo,
    ordenar_notas_por_dia_wheaton,
    ops_do_relatorio,
    ordenar_prefixos_por_troca,
    process_excel_desvios,
    process_excel_notas,
    process_excel_producao,
    separar_data_hora,
)
from utils.graficos import (
    gerar_grafico_comparativo_aq_af,
    gerar_graficos_desvios_por_op,
    gerar_graficos_por_prefixo,
)
from utils.openai_integration import get_anotacoes_interpretadas
from utils.pdf_processor import gerar_pdf_resumo_anotacoes


st.set_page_config(
    page_title="Relatório da Produção",
    layout="wide",
)

# Resultados da geração do relatório: são descartados sempre que um arquivo de
# entrada muda, porque deixam de corresponder aos dados em tela.
CHAVES_RELATORIO = (
    "anotacoes_resumidas",
    "json_interpretado",
    "resumo_anotacoes",
    "maquinas_resumidas",
    "graficos_relatorio",
    "graficos_desvios_relatorio",
)


def listar_em_texto(nomes: list[str]) -> str:
    """Junta os nomes em texto corrido: 'produção, notas e desvios'."""
    if len(nomes) < 2:
        return "".join(nomes)

    return f"{', '.join(nomes[:-1])} e {nomes[-1]}"


def limpar_relatorio() -> None:
    for chave in CHAVES_RELATORIO:
        st.session_state.pop(chave, None)


def carregar_arquivo(chave: str, arquivo, processar):
    """
    Processa o arquivo assim que ele é anexado e guarda o resultado na sessão,
    para não reprocessar a cada interação da tela. Devolve None enquanto o
    arquivo não for enviado ou se a leitura falhar.
    """
    if arquivo is None:
        if st.session_state.pop(chave, None) is not None:
            limpar_relatorio()
        return None

    processado = st.session_state.get(chave)

    if processado is not None and processado["id"] == arquivo.file_id:
        return processado["dados"]

    try:
        dados = processar(arquivo)
    except Exception as erro:
        st.session_state.pop(chave, None)
        st.sidebar.error(f"Não foi possível ler {arquivo.name}: {erro}")
        return None

    st.session_state[chave] = {"id": arquivo.file_id, "dados": dados}
    limpar_relatorio()

    return dados


def processar_desvios(arquivo):
    """Lê o excel de desvios e já monta os gráficos AQ x AF de cada OP."""
    df_desvios = process_excel_desvios(arquivo)

    return df_desvios, gerar_grafico_comparativo_aq_af(df_desvios)


st.title("Relatório Diário da Produção")
st.caption(
    "Anexe os arquivos na barra lateral: cada aba é liberada assim que a base "
    "correspondente chega."
)

# Toda a entrada de arquivos fica na barra lateral para que a área principal
# mostre apenas resultados.
with st.sidebar:
    st.header("Arquivos")

    # Produção e notas ficam no mesmo bloco porque se cruzam na mesma aba.
    with st.container(border=True):
        st.caption("**Desempenho diário** · as duas bases se cruzam na aba de desempenho.")

        excel_producao = st.file_uploader(
            "Excel de produção",
            type=["xlsx"],
            key="file_uploader_producao",
            accept_multiple_files=False,
        )

        excel_notas = st.file_uploader(
            "Bloco de notas",
            type=["xlsx"],
            key="file_uploader_notas",
            accept_multiple_files=False,
        )

    excel_desvios = st.file_uploader(
        "Excel de desvios",
        type=["xlsx"],
        key="file_uploader_desvios",
        accept_multiple_files=False,
    )

    excel_areas = st.file_uploader(
        "Excel de zonas de entrada",
        type=["xlsx"],
        key="file_uploader_areas",
        accept_multiple_files=False,
        help="Ainda não entra no relatório.",
    )

# Cada arquivo é processado por conta própria: dá para consultar os desvios
# sem ter enviado a produção, por exemplo.
producao = carregar_arquivo(
    "dados_producao",
    excel_producao,
    process_excel_producao,
)
desempenho, desempenho_hora_hora = (
    producao if producao is not None else (None, None)
)

df_notas = carregar_arquivo("dados_notas", excel_notas, process_excel_notas)

desvios = carregar_arquivo("dados_desvios", excel_desvios, processar_desvios)
df_desvios, graficos_aq_af = desvios if desvios is not None else (None, None)

# As máquinas abaixo do objetivo marcam a tabela, o seletor de máquina e o
# rodapé, por isso são calculadas antes das abas.
maquinas_abaixo_objetivo = (
    get_maquinas_abaixo_objetivo(desempenho) if desempenho is not None else []
)

desempenho_diario, aba_desvios, aba_zonas = st.tabs(
    ["Desempenho Diário", "Desvios", "Zonas de Entrada"]
)

with desempenho_diario:
    if desempenho is None:
        st.info(
            "Envie o excel de produção na barra lateral para ver o "
            "desempenho do dia.",
            icon=":material/upload_file:",
        )
    else:
        desempenho_exibicao = desempenho.reset_index()

        indicador_maquinas, indicador_abaixo, indicador_media = st.columns(3)

        indicador_maquinas.metric(
            "Máquinas no dia",
            desempenho_exibicao["Maquina"].nunique(),
            border=True,
        )
        indicador_abaixo.metric(
            "Abaixo do objetivo",
            len(maquinas_abaixo_objetivo),
            border=True,
            help="Entram no relatório diário.",
        )
        indicador_media.metric(
            "Média emp. - rejeitado",
            f"{desempenho_exibicao['Emp - Rejeitado %'].mean():.2f}%",
            border=True,
        )

        st.subheader("Resumo do dia")

        visualizacao = st.pills(
            "Visualização",
            ["Geral", "Abaixo do objetivo", "No objetivo ou acima"],
            default="Geral",
            selection_mode="single",
            label_visibility="collapsed",
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

        if desempenho_exibicao.empty:
            st.caption("Nenhuma máquina nesta visualização.")
        else:
            st.dataframe(
                tabela_estilizada,
                width="stretch",
            )

        st.divider()
        st.subheader("Hora a Hora")

        maquinas_disponiveis = (
            desempenho_hora_hora["Maquina"].dropna().unique().tolist()
        )

        if not maquinas_disponiveis:
            st.warning(
                "Não há dados hora a hora disponíveis para visualização.",
                icon=":material/warning:",
            )
        else:
            coluna_maquina, coluna_prefixo = st.columns(2)

            with coluna_maquina:
                maquina_selecionada = st.selectbox(
                    "Máquina",
                    options=maquinas_disponiveis,
                    key="maquina_hora_hora"
                )

            prefixos_disponiveis = ordenar_prefixos_por_troca(
                desempenho_hora_hora,
                maquina_selecionada,
            )
            prefixo_unico = len(prefixos_disponiveis) == 1

            with coluna_prefixo:
                prefixo_selecionado = st.selectbox(
                    "Prefixo",
                    options=prefixos_disponiveis,
                    key="prefixo_hora_hora",
                    disabled=prefixo_unico,
                    help=(
                        "Prefixo único desta máquina no dia."
                        if prefixo_unico
                        else "A máquina trocou de prefixo durante o dia."
                    ),
                )

            # Mesma leitura de cor da tabela, agora no texto da máquina
            # selecionada.
            if maquina_selecionada in maquinas_abaixo_objetivo:
                st.caption(
                    f":red[**{maquina_selecionada}** ficou abaixo do objetivo "
                    "do dia.]"
                )
            else:
                st.caption(
                    f":green[**{maquina_selecionada}** atingiu o objetivo "
                    "do dia.]"
                )

            figura = gerar_grafico_desempenho_hora_hora(
                desempenho_hora_hora,
                maquina_selecionada,
                prefixo_selecionado,
            )

            st.plotly_chart(figura, width="stretch")

            st.subheader("Anotações do dia")

            if df_notas is None:
                st.info(
                    "Envie o bloco de notas na barra lateral para ver as "
                    "anotações da máquina.",
                    icon=":material/upload_file:",
                )
            else:
                df_notas_filtrado = df_notas.loc[
                    df_notas["Maquina"] == maquina_selecionada
                ]

                if df_notas_filtrado.empty:
                    st.caption(
                        f"Sem anotações registradas para a máquina "
                        f"{maquina_selecionada}."
                    )
                else:
                    st.dataframe(
                        separar_data_hora(
                            ordenar_notas_por_dia_wheaton(df_notas_filtrado)
                        ),
                        width="stretch",
                        hide_index=True,
                    )

with aba_desvios:
    if df_desvios is None:
        st.info(
            "Envie o excel de desvios na barra lateral para ver a comparação "
            "entre AQ e AF.",
            icon=":material/upload_file:",
        )
    else:
        st.subheader("Top 5 desvios por localização")
        st.caption(
            f"{len(df_desvios)} registros · "
            f"{df_desvios['OP Vertech'].nunique()} OPs no arquivo."
        )

        if not graficos_aq_af:
            st.warning(
                "Nenhuma OP do arquivo tem desvios registrados nas duas "
                "localizações (AQ e AF).",
                icon=":material/warning:",
            )
        else:
            op_selecionada = st.selectbox(
                "OP Vertech",
                options=list(graficos_aq_af),
                key="op_desvios",
                help="Só aparecem as OPs com desvios em AQ e em AF.",
            )

            st.plotly_chart(
                graficos_aq_af[op_selecionada],
                width="stretch",
            )

        with st.expander("Dados do arquivo de desvios"):
            st.dataframe(df_desvios, width="stretch", hide_index=True)

with aba_zonas: 

    if excel_areas is None:
        st.info(
            "Envie o excel de zonas de entrada na barra lateral.",
            icon=":material/upload_file:",
        )
    else:
        # TODO: processar os dados quando as zonas de entrada entrarem no
        # relatório.
        st.info(
            "Análise de zonas de entrada em construção.",
            icon=":material/construction:",
        )

# O rodapé fica fora das abas para ficar acessível em todas elas. O botão
# aparece desde o início, mas só fica clicável quando os três arquivos
# obrigatórios foram enviados.
arquivos_obrigatorios = {
    "produção": desempenho is not None,
    "notas": df_notas is not None,
    "desvios": df_desvios is not None,
}
arquivos_faltando = [
    nome for nome, enviado in arquivos_obrigatorios.items() if not enviado
]

pronto_para_relatorio = not arquivos_faltando and bool(maquinas_abaixo_objetivo)

with st.bottom:
    coluna_status, coluna_download, coluna_acao = st.columns(
        [5, 1.4, 1.4],
        vertical_alignment="center",
    )

    with coluna_status:
        if arquivos_faltando:
            st.badge(
                f"Faltam os arquivos de {listar_em_texto(arquivos_faltando)}",
                color="gray",
                icon=":material/pending:",
            )
        elif not maquinas_abaixo_objetivo:
            st.badge(
                "Nenhuma máquina ficou abaixo do objetivo diário",
                color="green",
                icon=":material/check_circle:",
            )
        else:
            st.badge(
                f"Abaixo do objetivo: {', '.join(maquinas_abaixo_objetivo)}",
                color="red",
                icon=":material/warning:",
            )

    # Preenchido depois da geração, para o download ficar ao lado do botão em
    # vez de ocupar uma linha inteira do rodapé.
    espaco_download = coluna_download.empty()

    with coluna_acao:
        gerar_relatorio = st.button(
            "Gerar relatório",
            type="primary" if pronto_para_relatorio else "secondary",
            disabled=not pronto_para_relatorio,
            width="stretch",
            help=(
                f"Envie os arquivos de {listar_em_texto(arquivos_faltando)} "
                "para liberar a geração."
                if arquivos_faltando
                else "O relatório inclui somente as máquinas abaixo do "
                "objetivo diário de desempenho."
            ),
        )

if pronto_para_relatorio:
    anotacoes_json = gerar_json_anotacoes_por_maquina(
        df_notas,
        maquinas_abaixo_objetivo,
    )
    desempenho_json = gerar_json_desempenho(
        maquinas_abaixo_objetivo,
        desempenho,
        desempenho_hora_hora,
    )
    chave_resumo = f"{anotacoes_json}{desempenho_json}"

    if gerar_relatorio:
        with st.bottom:
            try:
                with st.spinner(
                    "Interpretando anotações com IA..."
                ):
                    interpretacoes = asyncio.run(
                        get_anotacoes_interpretadas(anotacoes_json)
                    )
                    json_interpretado = aplicar_anotacoes_interpretadas(
                        desempenho_json,
                        interpretacoes,
                    )

                with st.spinner("Gerando gráficos do relatório..."):
                    graficos_relatorio = gerar_graficos_por_prefixo(
                        desempenho_hora_hora,
                        maquinas_abaixo_objetivo,
                    )
                    graficos_desvios_relatorio = gerar_graficos_desvios_por_op(
                        graficos_aq_af,
                        ops_do_relatorio(json_interpretado),
                    )
            except Exception as erro:
                st.error(f"Não foi possível gerar o relatório: {erro}")
            else:
                st.session_state["anotacoes_resumidas"] = chave_resumo
                st.session_state["json_interpretado"] = json_interpretado
                st.session_state["resumo_anotacoes"] = gerar_markdown_resumo(
                    json_interpretado
                )
                st.session_state["maquinas_resumidas"] = (
                    maquinas_abaixo_objetivo.copy()
                )
                st.session_state["graficos_relatorio"] = graficos_relatorio
                st.session_state["graficos_desvios_relatorio"] = (
                    graficos_desvios_relatorio
                )

    resumo_ia = st.session_state.get("resumo_anotacoes")
    json_interpretado = st.session_state.get("json_interpretado")
    resumo_corresponde_as_anotacoes = (
        st.session_state.get("anotacoes_resumidas") == chave_resumo
    )

    if resumo_corresponde_as_anotacoes and resumo_ia:
        pdf_relatorio = gerar_pdf_resumo_anotacoes(
            json_interpretado,
            st.session_state.get("graficos_relatorio"),
            st.session_state.get("graficos_desvios_relatorio"),
        )
        espaco_download.download_button(
            "Baixar PDF",
            data=pdf_relatorio,
            file_name="relatorio_diario.pdf",
            mime="application/pdf",
            type="primary",
            icon=":material/download:",
            width="stretch",
            on_click="ignore",
            help="Relatório gerado a partir dos arquivos enviados.",
        )
    elif resumo_corresponde_as_anotacoes:
        st.warning("A IA não retornou um resumo.", icon=":material/warning:")
