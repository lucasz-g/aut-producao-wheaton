# Relatorio Diario da Producao — app Streamlit
#
# A imagem traz o Chromium porque o kaleido 1.x usa um navegador headless para
# exportar os graficos do Plotly em PNG. Sem ele o PDF continua sendo gerado,
# mas sai sem os graficos (utils/graficos.py engole a falha de propósito).
FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Chromium + fontes para o kaleido. O choreographer (usado pelo kaleido) ja
# chama o Chromium com --no-sandbox e --disable-dev-shm-usage, entao nao e
# preciso nenhuma capability extra no container.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

ENV BROWSER_PATH=/usr/bin/chromium

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Usuario sem privilegios. O HOME precisa existir e ser gravavel: o Streamlit
# escreve em ~/.streamlit e o Chromium usa um perfil temporario.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser
ENV HOME=/home/appuser

# Configuracao do servidor via variaveis de ambiente, para o CMD ficar limpo.
ENV STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_FILE_WATCHER_TYPE=none \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4)"]

CMD ["streamlit", "run", "app.py"]
