# ========== Importando dados ==========
import atexit
import io
import sys
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio


# ========== Configuração das pastas de saída ==========
RAIZ_PROJETO = Path(__file__).resolve().parents[1]
PASTA_OUTPUTS = RAIZ_PROJETO / "outputs"
ARQUIVO_DADOS = (
    RAIZ_PROJETO
    / "analytics"
    / "data"
    / "raw"
    / "Relatório de Produção - Completo - Dados.xlsx"
)

INICIO_EXECUCAO = datetime.now()
ID_EXECUCAO = INICIO_EXECUCAO.strftime("%Y-%m-%d_%H-%M-%S-%f")[:-3]
PASTA_EXECUCAO = PASTA_OUTPUTS / ID_EXECUCAO

# Evita colisão caso duas execuções comecem no mesmo milissegundo.
contador_execucao = 1
while PASTA_EXECUCAO.exists():
    PASTA_EXECUCAO = PASTA_OUTPUTS / f"{ID_EXECUCAO}_{contador_execucao:02d}"
    contador_execucao += 1

PASTA_GRAFICOS_GERAIS = PASTA_EXECUCAO / "graficos_gerais"
PASTA_GRAFICOS_POR_OP = PASTA_EXECUCAO / "graficos_por_OP"
ARQUIVO_OUTPUT_TERMINAL = PASTA_EXECUCAO / "output_terminal.md"

PASTA_GRAFICOS_GERAIS.mkdir(parents=True, exist_ok=True)
PASTA_GRAFICOS_POR_OP.mkdir(parents=True, exist_ok=True)


class SaidaDuplicada:
    def __init__(self, terminal, buffer):
        self.terminal = terminal
        self.buffer = buffer

    @property
    def encoding(self):
        return self.terminal.encoding

    def write(self, texto):
        self.terminal.write(texto)
        self.buffer.write(texto)
        return len(texto)

    def flush(self):
        self.terminal.flush()
        self.buffer.flush()

    def isatty(self):
        return self.terminal.isatty()


OUTPUT_TERMINAL = io.StringIO()
STDOUT_ORIGINAL = sys.stdout
STDERR_ORIGINAL = sys.stderr
STATUS_EXECUCAO = "Concluída"

sys.stdout = SaidaDuplicada(STDOUT_ORIGINAL, OUTPUT_TERMINAL)
sys.stderr = SaidaDuplicada(STDERR_ORIGINAL, OUTPUT_TERMINAL)


def registrar_excecao(tipo, valor, rastreamento):
    global STATUS_EXECUCAO
    STATUS_EXECUCAO = "Falhou"
    traceback.print_exception(
        tipo,
        valor,
        rastreamento,
        file=sys.stderr,
    )


def salvar_output_terminal():
    fim_execucao = datetime.now()

    sys.stdout.flush()
    sys.stderr.flush()
    output_capturado = OUTPUT_TERMINAL.getvalue().rstrip()

    sys.stdout = STDOUT_ORIGINAL
    sys.stderr = STDERR_ORIGINAL

    conteudo_markdown = (
        "# Output da execução\n\n"
        f"- **Identificador:** `{PASTA_EXECUCAO.name}`\n"
        f"- **Início:** `{INICIO_EXECUCAO:%Y-%m-%d %H:%M:%S.%f}`\n"
        f"- **Fim:** `{fim_execucao:%Y-%m-%d %H:%M:%S.%f}`\n"
        f"- **Status:** {STATUS_EXECUCAO}\n"
        f"- **Pasta:** `{PASTA_EXECUCAO}`\n\n"
        "## Saída do terminal\n\n"
        "```text\n"
        f"{output_capturado}\n"
        "```\n"
    )

    ARQUIVO_OUTPUT_TERMINAL.write_text(
        conteudo_markdown,
        encoding="utf-8",
    )

    STDOUT_ORIGINAL.write(
        f"Output do terminal salvo: {ARQUIVO_OUTPUT_TERMINAL}\n"
    )
    STDOUT_ORIGINAL.flush()


sys.excepthook = registrar_excecao
atexit.register(salvar_output_terminal)

print(f"Início da execução: {INICIO_EXECUCAO:%Y-%m-%d %H:%M:%S.%f}")
print(f"Identificador da execução: {PASTA_EXECUCAO.name}")
print(f"Pasta da execução: {PASTA_EXECUCAO}")


TAMANHO_LOTE_EXPORTACAO = 20
FILA_EXPORTACAO = []


def exportar_lote_png():
    if not FILA_EXPORTACAO:
        return

    print(
        f"Exportando lote com {len(FILA_EXPORTACAO)} gráfico(s)..."
    )

    pio.write_images(
        fig=[item["fig"] for item in FILA_EXPORTACAO],
        file=[item["caminho"] for item in FILA_EXPORTACAO],
        format="png",
        width=[item["largura"] for item in FILA_EXPORTACAO],
        height=[item["altura"] for item in FILA_EXPORTACAO],
        scale=pio.defaults.default_scale,
    )

    for item in FILA_EXPORTACAO:
        print(f"Gráfico salvo: {item['caminho']}")

    FILA_EXPORTACAO.clear()


def salvar_figura_png(fig, nome_arquivo, op_vertech=None):
    if op_vertech is None:
        pasta_destino = PASTA_GRAFICOS_GERAIS
    else:
        nome_op = str(op_vertech).strip()

        if nome_op.endswith(".0") and nome_op[:-2].isdigit():
            nome_op = nome_op[:-2]

        for caractere in '<>:"/\\|?*':
            nome_op = nome_op.replace(caractere, "_")

        pasta_destino = PASTA_GRAFICOS_POR_OP / f"OP_{nome_op}"
        pasta_destino.mkdir(parents=True, exist_ok=True)

    caminho_arquivo = pasta_destino / f"{nome_arquivo}.png"
    layout_figura = fig.to_dict().get("layout", {})
    layout_template = (
        layout_figura
        .get("template", {})
        .get("layout", {})
    )

    largura = (
        layout_figura.get("width")
        or layout_template.get("width")
        or pio.defaults.default_width
    )
    altura = (
        layout_figura.get("height")
        or layout_template.get("height")
        or pio.defaults.default_height
    )

    FILA_EXPORTACAO.append({
        "fig": fig,
        "caminho": caminho_arquivo,
        "largura": largura,
        "altura": altura,
    })

    if len(FILA_EXPORTACAO) >= TAMANHO_LOTE_EXPORTACAO:
        exportar_lote_png()




# ========== Lendo dados ==========
df = pd.read_excel(ARQUIVO_DADOS)




# ========== Tratamento de dados - base diária ==========
df_diario = df.copy()

# Tratando o cabeçalho
df_diario.columns = df_diario.iloc[1]
df_diario = df_diario.iloc[2:].reset_index(drop=True)
df_diario.columns.name = None

# Convertendo as métricas para valores numéricos
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
    df_diario[coluna] = pd.to_numeric(
        df_diario[coluna]
        .astype("string")
        .str.strip()
        .str.replace("%", "", regex=False)
        .str.replace(",", ".", regex=False),
        errors="coerce",
    )

# Agrupando os registros horários pela produção identificada pela OP
desempenho_empacotamento_diario = (
    df_diario
    .groupby(
        "OP Vertech",
        as_index=False,
    )
    .agg({
        # Informações descritivas da produção
        "Data Wht (dia)": "first",
        "Maquina": "first",
        "Prefixo": "first",

        # Métricas da produção
        "Objetivo %": "min",
        "Empacotado %": "mean",
        "Rejeição %": "mean",
    })
)

# Calculando o desempenho depois da rejeição
desempenho_empacotamento_diario[
    "Emp - Rejeitado %"
] = (
    desempenho_empacotamento_diario["Empacotado %"]
    * (
        1
        - desempenho_empacotamento_diario["Rejeição %"]
    )
)




# ========== Tratamento de dados - base hora a hora ==========
# Tratando cabeçalho
df.columns = df.iloc[1]
df = df.iloc[2:].reset_index(drop=True)
df.columns.name = None

# Criando as variáveis de data e hora do dia produtivo (07h até 06h)
df["Hora Hora Wht (6to6)"] = pd.to_numeric(
    df["Hora Hora Wht (6to6)"],
    errors="coerce"
)

df["Data Wht (dia)"] = pd.to_datetime(
    df["Data Wht (dia)"],
    dayfirst=True,
    errors="coerce"
).dt.normalize()

df["Data_metrica"] = (
    df["Data Wht (dia)"]
    + pd.to_timedelta(
        df["Hora Hora Wht (6to6)"],
        unit="h"
    )
)

# Ordem operacional: 07h = 0, 08h = 1, ..., 23h = 16, 00h = 17, ..., 06h = 23
df["Ordem_Hora_Producao"] = (
    (df["Hora Hora Wht (6to6)"] - 7) % 24
)

# Chave técnica para ordenar vários dias produtivos sem alterar Data Wht (dia)
df["Data_Hora_Ordem_Producao"] = (
    df["Data Wht (dia)"]
    + pd.to_timedelta(
        df["Ordem_Hora_Producao"],
        unit="h"
    )
)

df["Hora_Producao"] = (
    df["Hora Hora Wht (6to6)"]
    .astype("Int64")
    .astype("string")
    .str.zfill(2)
    + ":00"
)

ORDEM_HORAS_PRODUCAO = [
    f"{hora:02d}:00"
    for hora in list(range(7, 24)) + list(range(0, 7))
]

# transformando variaveis numericas corretamente
colunas_numericas = [
    'Veloc Stand',
    'Veloc Real',
    'Qtd Teorica Real',
    'Corte de Gota %',
    'Objetivo %',
    'Qtd Objetivo',
    'Empacotado %',
    'Qtd Empacotado',
    'Rejeição %',
    'Qtd Rejeicao'
]

for coluna in colunas_numericas:
    df[coluna] = pd.to_numeric(df[coluna], errors='coerce')
    
# criando variavel "Emp - Rej"
df["Emp - Rej %"] = (
    df["Empacotado %"] - df["Rejeição %"]
)

df["Qtd Emp - Qtd Rej"] = (
    df["Qtd Empacotado"] - df["Qtd Rejeicao"]
)

# criando variavel de gap entre "Emp - Rej %" e "Objetivo %"
df['Gap_Obj %'] = (df['Emp - Rej %'] - df['Objetivo %'])
df['Qtd Gap_Obj'] = (df['Qtd Emp - Qtd Rej'] - df['Qtd Objetivo'])





# ========== Analises - Variacao "Emp - Rej %" ==========
# Ordena uma única vez, sem modificar o df original
df_analise = df.sort_values(
    "Data_Hora_Ordem_Producao"
)

# Turno, início, fim, posição do rótulo e cor
faixas_turnos = [
    ("Turno A", -0.5, 7, "10:00", "#D6EAF8"),
    ("Turno B", 7, 15, "18:00", "#AED6F1"),
    ("Turno C", 15, 23.5, "02:00", "#85C1E9"),
]

# Cria um gráfico para cada OP
for op_vertech, dados_op in df_analise.groupby("OP Vertech"):
    fig = px.line(
        dados_op,
        x="Hora_Producao",
        y="Emp - Rej %",
        markers=True,
        color_discrete_sequence=["#3366CC"],
        category_orders={
            "Hora_Producao": ORDEM_HORAS_PRODUCAO
        },
        title=(
            f'Variação de "Emp - Rej %" da '
            f"OP {op_vertech} hora a hora"
        ),
        labels={
            "Hora_Producao": "Hora do dia produtivo"
        },
        hover_data=[
            "OP Vertech",
            "Qtd Empacotado",
            "Rejeição %",
            "Qtd Rejeicao",
            "Objetivo %",
            "Qtd Objetivo",
        ],
    )

    # Adiciona as faixas e os rótulos dos turnos
    for turno, inicio, fim, hora_rotulo, cor in faixas_turnos:
        fig.add_vrect(
            x0=inicio,
            x1=fim,
            fillcolor=cor,
            opacity=0.35,
            line_width=0,
            layer="below",
        )

        fig.add_annotation(
            x=hora_rotulo,
            y=0.98,
            xref="x",
            yref="paper",
            text=turno,
            showarrow=False,
            font={
                "size": 12,
                "color": "#34495E",
            },
            bgcolor="rgba(255, 255, 255, 0.70)",
            borderpad=3,
        )

    # Linhas pontilhadas às 14h e às 22h
    for limite in (7, 15):
        fig.add_shape(
            type="line",
            x0=limite,
            x1=limite,
            y0=0,
            y1=1,
            xref="x",
            yref="paper",
            line={
                "color": "rgba(52, 73, 94, 0.75)",
                "width": 1.5,
                "dash": "dot",
            },
            layer="above",
        )

    fig.update_yaxes(
        tickformat=".0%"
    )

    fig.update_layout(
        title_x=0.5,
        height=600,
        width=1000,
        showlegend=False,
        margin={
            "l": 80,
            "r": 60,
            "t": 90,
            "b": 70,
        },
    )

    salvar_figura_png(
        fig,
        "variacao_emp_rej_percentual_hora_a_hora",
        op_vertech,
    )





# ========== Analise - Variacao "Empacotado %" =============
# Ordena uma única vez, sem modificar o df original
df_analise = df.sort_values(
    "Data_Hora_Ordem_Producao"
)

# Turno, início, fim, posição do rótulo e cor
faixas_turnos = [
    ("Turno A", -0.5, 7, "10:00", "#D6EAF8"),
    ("Turno B", 7, 15, "18:00", "#AED6F1"),
    ("Turno C", 15, 23.5, "02:00", "#85C1E9"),
]

# Cria um gráfico separado para cada OP
for op_vertech, dados_op in df_analise.groupby("OP Vertech"):
    fig = px.line(
        dados_op,
        x="Hora_Producao",
        y="Empacotado %",
        markers=True,
        color_discrete_sequence=["#3366CC"],
        category_orders={
            "Hora_Producao": ORDEM_HORAS_PRODUCAO
        },
        title=(
            f'Variação de "Empacotado %" da '
            f"OP {op_vertech} hora a hora"
        ),
        labels={
            "Hora_Producao": "Hora do dia produtivo"
        },
        hover_data=[
            "OP Vertech",
            "Qtd Empacotado",
            "Rejeição %",
            "Qtd Rejeicao",
            "Objetivo %",
            "Qtd Objetivo",
        ],
    )

    # Adiciona as faixas e os rótulos dos turnos
    for turno, inicio, fim, hora_rotulo, cor in faixas_turnos:
        fig.add_vrect(
            x0=inicio,
            x1=fim,
            fillcolor=cor,
            opacity=0.35,
            line_width=0,
            layer="below",
        )

        fig.add_annotation(
            x=hora_rotulo,
            y=0.98,
            xref="x",
            yref="paper",
            text=turno,
            showarrow=False,
            font={
                "size": 12,
                "color": "#34495E",
            },
            bgcolor="rgba(255, 255, 255, 0.70)",
            borderpad=3,
        )

    # Linhas pontilhadas às 14h e às 22h
    for limite in (7, 15):
        fig.add_shape(
            type="line",
            x0=limite,
            x1=limite,
            y0=0,
            y1=1,
            xref="x",
            yref="paper",
            line={
                "color": "rgba(52, 73, 94, 0.75)",
                "width": 1.5,
                "dash": "dot",
            },
            layer="above",
        )

    # Formata os valores do eixo Y como percentuais
    fig.update_yaxes(
        tickformat=".0%"
    )

    fig.update_layout(
        title_x=0.5,
        height=600,
        width=1000,
        showlegend=False,
        margin={
            "l": 80,
            "r": 60,
            "t": 90,
            "b": 70,
        },
    )

    salvar_figura_png(
        fig,
        "variacao_empacotado_percentual_hora_a_hora",
        op_vertech,
    )





# ========== Analise - Variacao "Rejeicao %" =============
# Ordena uma única vez, sem modificar o df original
df_analise = df.sort_values(
    "Data_Hora_Ordem_Producao"
)

# Turno, início, fim, posição do rótulo e cor
faixas_turnos = [
    ("Turno A", -0.5, 7, "10:00", "#D6EAF8"),
    ("Turno B", 7, 15, "18:00", "#AED6F1"),
    ("Turno C", 15, 23.5, "02:00", "#85C1E9"),
]

# Cria um gráfico separado para cada OP
for op_vertech, dados_op in df_analise.groupby("OP Vertech"):
    fig = px.line(
        dados_op,
        x="Hora_Producao",
        y="Rejeição %",
        markers=True,
        color_discrete_sequence=["#3366CC"],
        category_orders={
            "Hora_Producao": ORDEM_HORAS_PRODUCAO
        },
        title=(
            f'Variação de "Rejeição %" da '
            f"OP {op_vertech} hora a hora"
        ),
        labels={
            "Hora_Producao": "Hora do dia produtivo"
        },
        hover_data=[
            "OP Vertech",
            "Qtd Rejeicao",
            "Empacotado %",
            "Qtd Empacotado",
            "Objetivo %",
            "Qtd Objetivo",
        ],
    )

    # Adiciona as faixas e os rótulos dos turnos
    for turno, inicio, fim, hora_rotulo, cor in faixas_turnos:
        fig.add_vrect(
            x0=inicio,
            x1=fim,
            fillcolor=cor,
            opacity=0.35,
            line_width=0,
            layer="below",
        )

        fig.add_annotation(
            x=hora_rotulo,
            y=0.98,
            xref="x",
            yref="paper",
            text=turno,
            showarrow=False,
            font={
                "size": 12,
                "color": "#34495E",
            },
            bgcolor="rgba(255, 255, 255, 0.70)",
            borderpad=3,
        )

    # Linhas pontilhadas às 14h e às 22h
    for limite in (7, 15):
        fig.add_shape(
            type="line",
            x0=limite,
            x1=limite,
            y0=0,
            y1=1,
            xref="x",
            yref="paper",
            line={
                "color": "rgba(52, 73, 94, 0.75)",
                "width": 1.5,
                "dash": "dot",
            },
            layer="above",
        )

    # Formata os valores do eixo Y como percentuais
    fig.update_yaxes(
        tickformat=".0%"
    )

    fig.update_layout(
        title_x=0.5,
        height=600,
        width=1000,
        showlegend=False,
        margin={
            "l": 80,
            "r": 60,
            "t": 90,
            "b": 70,
        },
    )

    salvar_figura_png(
        fig,
        "variacao_rejeicao_percentual_hora_a_hora",
        op_vertech,
    )





# ========== Analise - Gap entre "Emp - Rej %" e "Objetivo %" =============
# Ordena uma única vez, sem modificar o df original
df_analise = df.sort_values(
    "Data_Hora_Ordem_Producao"
)

# Turno, início, fim, posição do rótulo e cor
faixas_turnos = [
    ("Turno A", -0.5, 7, "10:00", "#D6EAF8"),
    ("Turno B", 7, 15, "18:00", "#AED6F1"),
    ("Turno C", 15, 23.5, "02:00", "#85C1E9"),
]

# Cria um gráfico separado para cada OP
for op_vertech, dados_op in df_analise.groupby("OP Vertech"):
    fig = px.line(
        dados_op,
        x="Hora_Producao",
        y="Gap_Obj %",
        markers=True,
        color_discrete_sequence=["#3366CC"],
        category_orders={
            "Hora_Producao": ORDEM_HORAS_PRODUCAO
        },
        title=(
            f'Gap entre "Emp - Rej %" e "Objetivo %" '
            f"da OP {op_vertech} hora a hora"
        ),
        labels={
            "Hora_Producao": "Hora do dia produtivo",
            "Gap_Obj %": "Gap em relação ao objetivo",
        },
        hover_data=[
            "OP Vertech",
            "Qtd Gap_Obj",
            "Objetivo %",
            "Qtd Objetivo",
            "Empacotado %",
            "Qtd Empacotado",
            "Rejeição %",
            "Qtd Rejeicao",
            "Emp - Rej %",
            "Qtd Emp - Qtd Rej",
        ],
    )

    # Adiciona as faixas e os rótulos dos turnos
    for turno, inicio, fim, hora_rotulo, cor in faixas_turnos:
        fig.add_vrect(
            x0=inicio,
            x1=fim,
            fillcolor=cor,
            opacity=0.35,
            line_width=0,
            layer="below",
        )

        fig.add_annotation(
            x=hora_rotulo,
            y=0.98,
            xref="x",
            yref="paper",
            text=turno,
            showarrow=False,
            font={
                "size": 12,
                "color": "#34495E",
            },
            bgcolor="rgba(255, 255, 255, 0.70)",
            borderpad=3,
        )

    # Linhas pontilhadas às 14h e às 22h
    for limite in (7, 15):
        fig.add_shape(
            type="line",
            x0=limite,
            x1=limite,
            y0=0,
            y1=1,
            xref="x",
            yref="paper",
            line={
                "color": "rgba(52, 73, 94, 0.75)",
                "width": 1.5,
                "dash": "dot",
            },
            layer="above",
        )

    # Linha horizontal que representa o cumprimento exato do objetivo
    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color="black",
        line_width=2,
        annotation_text="Ponto de equilíbrio",
        annotation_position="top left",
    )

    # Formata o eixo Y e mantém a escala automática por OP
    fig.update_yaxes(
        tickformat=".0%"
    )

    fig.update_layout(
        title_x=0.5,
        height=600,
        width=1000,
        showlegend=False,
        margin={
            "l": 80,
            "r": 60,
            "t": 90,
            "b": 70,
        },
    )

    salvar_figura_png(
        fig,
        "gap_objetivo_percentual_hora_a_hora",
        op_vertech,
    )





# ========== Analise - Horas abaixo do objetivo ==========
# A OP Vertech será a chave de cada produção
chave_analise = "OP Vertech"

# Identifica cada registro horário abaixo do objetivo
df["Abaixo do Objetivo"] = (
    df["Qtd Empacotado"]
    < df["Qtd Objetivo"]
)

# Quantidade total de registros horários da OP
df["Quantidade Total de Horas Trabalhadas"] = (
    df
    .groupby(
        chave_analise,
        dropna=False,
    )["Abaixo do Objetivo"]
    .transform("size")
)

# Quantidade de horas da OP abaixo do objetivo
df["Quantidade de Horas Abaixo do Objetivo"] = (
    df
    .groupby(
        chave_analise,
        dropna=False,
    )["Abaixo do Objetivo"]
    .transform("sum")
)

# Percentual das horas da OP abaixo do objetivo
df["Percentual de Horas Abaixo do Objetivo"] = (
    df
    .groupby(
        chave_analise,
        dropna=False,
    )["Abaixo do Objetivo"]
    .transform("mean")
    .mul(100)
)

# Cria uma tabela com uma linha por OP
resumo_horas_abaixo_objetivo_por_op = (
    df[
        [
            "OP Vertech",
            "Maquina",
            "Prefixo",
            "Quantidade Total de Horas Trabalhadas",
            "Quantidade de Horas Abaixo do Objetivo",
            "Percentual de Horas Abaixo do Objetivo",
        ]
    ]
    .drop_duplicates(subset=["OP Vertech"])
    .sort_values("OP Vertech")
    .reset_index(drop=True)
)

pct = "Percentual de Horas Abaixo do Objetivo"
total = "Quantidade Total de Horas Trabalhadas"
abaixo = "Quantidade de Horas Abaixo do Objetivo"
grupo = "OP"

df_grafico = (
    resumo_horas_abaixo_objetivo_por_op
    .assign(**{
        grupo: lambda dados: (
            dados["OP Vertech"].astype(str)
        )
    })
    .sort_values(pct)
)

fig = px.bar(
    df_grafico,
    x=pct,
    y=grupo,
    orientation="h",
    color=pct,
    text=pct,
    color_continuous_scale="RdYlGn_r",
    range_color=[0, 100],
    title="Percentual de Horas Abaixo do Objetivo por OP",
    labels={
        pct: "Horas abaixo do objetivo (%)",
        grupo: "OP Vertech",
        total: "Total de horas da OP",
        abaixo: "Horas abaixo do objetivo",
        "Maquina": "Máquina",
        "Prefixo": "Prefixo",
    },
    hover_data={
        "Maquina": True,
        "Prefixo": True,
        total: True,
        abaixo: True,
        pct: ":.2f",
    },
    template="plotly_white",
)

fig.update_traces(
    texttemplate="%{text:.1f}%",
    textposition="outside",
    cliponaxis=False,
)

fig.update_xaxes(
    range=[0, 105],
    ticksuffix="%",
    dtick=10,
)

fig.update_yaxes(
    categoryorder="total ascending"
)

fig.update_layout(
    title_x=0.5,
    coloraxis_colorbar={
        "title": "Percentual",
        "ticksuffix": "%",
    },
    height=700,
    margin={
        "l": 100,
        "r": 60,
        "t": 80,
        "b": 60,
    },
)

salvar_figura_png(
    fig,
    "percentual_horas_abaixo_objetivo_por_op",
)





# ========== Analise - Resumo diário das métricas das OPs ==========
indicadores = [
    "Empacotado %",
    "Objetivo %",
    "Rejeição %",
    "Emp - Rejeitado %",
]

cores_indicadores = {
    "Empacotado %": "#3366CC",
    "Objetivo %": "#2CA02C",
    "Rejeição %": "#FF7F0E",
    "Emp - Rejeitado %": "#F2C80F",
}

# Prepara e ordena as OPs da menor para a maior performance
base_grafico = (
    desempenho_empacotamento_diario
    .assign(**{
        "OP Vertech": lambda dados:
            dados["OP Vertech"].astype(str)
    })
    .sort_values(
        "Emp - Rejeitado %",
        ascending=True,
    )
)

# Cria um gráfico separado para cada OP
for op_vertech, dados_op in base_grafico.groupby(
    "OP Vertech",
    sort=False,
):
    # Transforma os quatro indicadores em linhas
    dados_plot = dados_op.melt(
        id_vars=[
            "OP Vertech",
            "Data Wht (dia)",
            "Maquina",
            "Prefixo",
        ],
        value_vars=indicadores,
        var_name="Indicador",
        value_name="Percentual",
    )

    fig = px.bar(
        dados_plot,
        x="OP Vertech",
        y="Percentual",
        color="Indicador",
        barmode="group",
        category_orders={
            "Indicador": indicadores
        },
        color_discrete_map=cores_indicadores,
        title=(
            f"Resumo Diário de Empacotamento, Objetivo, "
            f"Rejeição e Desempenho da OP {op_vertech}"
        ),
        labels={
            "OP Vertech": "OP",
            "Percentual": "Percentual",
            "Indicador": "Métrica",
            "Data Wht (dia)": "Data de produção",
            "Maquina": "Máquina",
            "Prefixo": "Prefixo",
        },
        hover_data={
            "Data Wht (dia)": True,
            "Maquina": True,
            "Prefixo": True,
            "Percentual": ":.2%",
        },
        template="plotly_white",
    )

    fig.update_traces(
        texttemplate="%{y:.1%}",
        textposition="outside",
        cliponaxis=False,
    )

    fig.update_yaxes(
        tickformat=".0%",
        title="Percentual",
        showgrid=True,
    )

    fig.update_xaxes(
        title="OP Vertech",
    )

    fig.update_layout(
        title_x=0.5,
        legend_title="Indicador",
        bargap=0.25,
        bargroupgap=0.08,
        height=600,
        width=900,
        margin={
            "l": 80,
            "r": 60,
            "t": 80,
            "b": 80,
        },
    )

    salvar_figura_png(
        fig,
        "resumo_diario_metricas",
        op_vertech,
    )


exportar_lote_png()
print("Execução concluída com sucesso.")






