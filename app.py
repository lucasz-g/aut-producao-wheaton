import streamlit as st
import pandas as pd


st.title("Relatório de Produção")

excel_producao = st.file_uploader("Upload do excel de produção", type=["xlsx"], key="file_uploader_producao")
if excel_producao:
    st.write("Arquivo carregado com sucesso!")

# excel_notas = st.file_uploader("Upload do bloco de notas", type=["xlsx"], key="file_uploader_notas")
# if excel_notas:
#     st.write("Arquivo carregado com sucesso!")