# Automação de Relatórios de Produção

Projeto em fase inicial para leitura e análise de relatórios de produção com Python, pandas e Streamlit.

## Pré-requisitos

- Python 3.13 instalado;
- Git instalado;
- PowerShell.

O projeto foi iniciado e validado localmente com Python 3.13.0.

## Configuração do ambiente

Abra o PowerShell na pasta do projeto e crie um ambiente virtual:

```powershell
python -m venv venv
```

Ative o ambiente:

```powershell
.\venv\Scripts\Activate.ps1
```

Se a ativação funcionar, o terminal exibirá `(venv)` no início da linha.

Instale as dependências:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Executando a aplicação

Com o ambiente virtual ativo, execute:

```powershell
streamlit run app.py
```

O Streamlit informará no terminal o endereço local da aplicação, normalmente `http://localhost:8501`.

## Dependências principais

- `streamlit`: cria a interface web;
- `pandas`: organiza e transforma os dados;
- `openpyxl`: permite ao pandas ler arquivos Excel no formato `.xlsx`.

## Dados locais

As planilhas dentro de `analytics/data/` não são enviadas ao GitHub. Essa regra evita publicar dados de produção por engano.

Cada desenvolvedor deve colocar manualmente nessa pasta os arquivos necessários para executar os notebooks. A aplicação Streamlit recebe a planilha pelo campo de upload.

## Encerrando o ambiente virtual

Quando terminar o trabalho, execute:

```powershell
deactivate
```
