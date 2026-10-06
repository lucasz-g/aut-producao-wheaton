"""Unifica várias planilhas do Excel em um único arquivo, uma aba por planilha.

Uso padrão (une os quatro relatórios de analytics/data/raw):

    python scripts/unificador_de_planilhas.py

Escolhendo os arquivos e o destino:

    python scripts/unificador_de_planilhas.py arquivo1.xlsx arquivo2.xlsx -s saida.xlsx

Observação: a unificação copia apenas os dados (valores, cabeçalhos e ordem das
colunas). Formatação, fórmulas, gráficos e imagens dos arquivos de origem não são
preservados no arquivo final.
"""

# ========== Importando dados ==========
import argparse
import sys
from pathlib import Path

import pandas as pd


# ========== Configuração das pastas e dos arquivos ==========
RAIZ_PROJETO = Path(__file__).resolve().parents[1]
PASTA_RAW = RAIZ_PROJETO / "analytics" / "data" / "raw"
PASTA_PROCESSED = RAIZ_PROJETO / "analytics" / "data" / "processed"

# Planilhas unificadas por padrão, na ordem em que as abas serão criadas.
ARQUIVOS_PADRAO = [
    PASTA_RAW / "Zonas e Perdas (sensor).xlsx",
    PASTA_RAW / "Relatório de Produção - Completo - Bloco de Notas.xlsx",
    PASTA_RAW / "Relatório de Produção - Completo - Dados.xlsx",
    PASTA_RAW / "Desvios por máquina - Completo.xlsx",
]

ARQUIVO_SAIDA_PADRAO = PASTA_PROCESSED / "Planilhas Unificadas.xlsx"

# Limites impostos pelo próprio Excel para o nome de uma aba.
LIMITE_NOME_ABA = 31
CARACTERES_PROIBIDOS_ABA = set(r"[]:*?/\\")


# ========== Funções auxiliares ==========
def limpar_nome_aba(nome):
    """Remove os caracteres que o Excel não aceita no nome de uma aba."""
    nome_limpo = "".join(
        " " if caractere in CARACTERES_PROIBIDOS_ABA else caractere
        for caractere in str(nome)
    )
    # Espaços duplicados aparecem depois da troca acima; colapsa e apara as pontas.
    nome_limpo = " ".join(nome_limpo.split()).strip("'")
    return nome_limpo or "Aba"


def encurtar_nome_aba(nome, limite=LIMITE_NOME_ABA):
    """Garante que o nome caiba no limite de 31 caracteres do Excel.

    O corte é no meio do nome, e não no fim, porque os relatórios só se
    diferenciam pelo final ("... - Dados" x "... - Bloco de Notas"): cortar o fim
    produziria abas com o mesmo nome.
    """
    if len(nome) <= limite:
        return nome
    espaco = limite - 1  # Um caractere fica reservado para a reticência.
    inicio = espaco // 2
    fim = espaco - inicio
    return f"{nome[:inicio].rstrip()}…{nome[-fim:].lstrip()}"


def tornar_nome_unico(nome, nomes_usados):
    """Acrescenta um sufixo numérico caso o nome de aba já tenha sido usado."""
    if nome not in nomes_usados:
        nomes_usados.add(nome)
        return nome

    contador = 2
    while True:
        sufixo = f" ({contador})"
        candidato = encurtar_nome_aba(nome, LIMITE_NOME_ABA - len(sufixo)) + sufixo
        if candidato not in nomes_usados:
            nomes_usados.add(candidato)
            return candidato
        contador += 1


def montar_nome_aba(arquivo, nome_aba_origem, arquivo_tem_varias_abas, nomes_usados):
    """Define o nome da aba no arquivo unificado.

    Arquivos com uma única aba viram uma aba com o nome do arquivo. Arquivos com
    várias abas geram uma aba por planilha, no formato "arquivo - aba", para que
    dê para saber de onde cada uma veio.
    """
    nome_arquivo = limpar_nome_aba(arquivo.stem)
    if not arquivo_tem_varias_abas:
        nome_final = encurtar_nome_aba(nome_arquivo)
    else:
        nome_final = encurtar_nome_aba(
            f"{nome_arquivo} - {limpar_nome_aba(nome_aba_origem)}"
        )
    return tornar_nome_unico(nome_final, nomes_usados)


def ler_planilha(arquivo):
    """Lê todas as abas de um arquivo do Excel, preservando a ordem original."""
    return pd.read_excel(arquivo, sheet_name=None, dtype=object)


def ajustar_largura_colunas(planilha, dados):
    """Deixa as colunas largas o suficiente para o conteúdo ficar legível."""
    for indice, coluna in enumerate(dados.columns, start=1):
        valores = dados.iloc[:, indice - 1]
        tamanhos = [len(str(valor)) for valor in valores if pd.notna(valor)]
        largura = max([len(str(coluna))] + tamanhos) + 2
        planilha.column_dimensions[
            planilha.cell(row=1, column=indice).column_letter
        ].width = min(largura, 50)


# ========== Unificação ==========
def unificar_planilhas(arquivos, arquivo_saida, ajustar_colunas=True):
    """Escreve todas as abas dos arquivos informados em um único arquivo do Excel."""
    arquivos_existentes = []
    for arquivo in arquivos:
        if arquivo.is_file():
            arquivos_existentes.append(arquivo)
        else:
            print(f"[AVISO] Arquivo não encontrado, será ignorado: {arquivo}")

    if not arquivos_existentes:
        raise FileNotFoundError(
            "Nenhum dos arquivos informados foi encontrado; nada a unificar."
        )

    arquivo_saida.parent.mkdir(parents=True, exist_ok=True)

    nomes_usados = set()
    total_abas = 0

    with pd.ExcelWriter(arquivo_saida, engine="openpyxl") as escritor:
        for arquivo in arquivos_existentes:
            print(f"Lendo: {arquivo.name}")
            abas = ler_planilha(arquivo)
            tem_varias_abas = len(abas) > 1

            for nome_aba_origem, dados in abas.items():
                nome_aba = montar_nome_aba(
                    arquivo, nome_aba_origem, tem_varias_abas, nomes_usados
                )
                dados.to_excel(escritor, sheet_name=nome_aba, index=False)

                if ajustar_colunas:
                    ajustar_largura_colunas(escritor.sheets[nome_aba], dados)

                print(
                    f"   aba '{nome_aba_origem}' -> '{nome_aba}' "
                    f"({len(dados)} linhas x {len(dados.columns)} colunas)"
                )
                total_abas += 1

    print(f"\nArquivo unificado gerado com {total_abas} aba(s): {arquivo_saida}")
    return arquivo_saida


# ========== Execução via linha de comando ==========
def montar_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Une várias planilhas do Excel em um único arquivo, "
            "colocando cada planilha em uma aba."
        )
    )
    parser.add_argument(
        "arquivos",
        nargs="*",
        type=Path,
        help=(
            "Arquivos .xlsx a unificar. Sem nenhum argumento, usa os quatro "
            "relatórios padrão de analytics/data/raw."
        ),
    )
    parser.add_argument(
        "-s",
        "--saida",
        type=Path,
        default=ARQUIVO_SAIDA_PADRAO,
        help=f"Arquivo de saída (padrão: {ARQUIVO_SAIDA_PADRAO}).",
    )
    parser.add_argument(
        "--sem-ajuste-de-colunas",
        action="store_true",
        help="Não ajusta a largura das colunas do arquivo gerado.",
    )
    return parser


def main(argumentos=None):
    parser = montar_parser()
    opcoes = parser.parse_args(argumentos)

    arquivos = opcoes.arquivos or ARQUIVOS_PADRAO
    arquivos = [Path(arquivo).expanduser().resolve() for arquivo in arquivos]

    try:
        unificar_planilhas(
            arquivos,
            Path(opcoes.saida).expanduser().resolve(),
            ajustar_colunas=not opcoes.sem_ajuste_de_colunas,
        )
    except FileNotFoundError as erro:
        print(f"[ERRO] {erro}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
