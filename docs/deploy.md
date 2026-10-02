# Deploy do Relatorio Diario da Producao

A aplicacao roda como um unico container Docker: um servico Streamlit, sem banco
de dados e sem volume. Tudo que o app recebe (os dois Excel) e produz (o PDF)
fica em memoria durante a sessao.

Dois caminhos, ambos usando o mesmo `docker-compose.yml`:

- **[SSH na VM](#deploy-por-ssh-recomendado)** — recomendado.
- **[Stack no Portainer](#alternativa-stack-no-portainer)** — se preferir
  gerenciar pela UI.

## Arquivos usados

| Arquivo | Papel |
| --- | --- |
| `Dockerfile` | imagem da aplicacao (Python 3.13 + Chromium para os graficos) |
| `docker-compose.yml` | define o servico, a porta e as variaveis |
| `.dockerignore` | mantem `venv/`, `analytics/data/`, `outputs/` e `.env` fora da imagem |
| `scripts/deploy.sh` | atualiza o codigo e recria o container na VM |

---

## Deploy por SSH (recomendado)

VM: `ssh inovacao@68.154.1.107`

### Primeira vez

```bash
ssh inovacao@68.154.1.107

# 1. Docker, se ainda nao estiver instalado
docker --version || curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"   # saia e entre de novo na sessao SSH

# 2. Clonar o repositorio
sudo mkdir -p /opt/automacao-relatorios
sudo chown "$USER":"$USER" /opt/automacao-relatorios
git clone <URL_DO_REPOSITORIO> /opt/automacao-relatorios
cd /opt/automacao-relatorios

# 3. Criar o .env com a credencial da Azure OpenAI
cp .env.example .env
nano .env        # preencha AZURE_OPENAI_API_KEY
chmod 600 .env

# 4. Subir
docker compose up -d --build
```

O `.env` fica **so na VM** — ele esta no `.gitignore` e no `.dockerignore`, e
nunca entra no repositorio nem na imagem. O `docker compose` le esse arquivo
automaticamente para preencher as variaveis do compose.

Libere a porta `8501` no **Network Security Group da VM no Azure**, senao o app
sobe mas ninguem acessa.

### Atualizacoes

```bash
ssh inovacao@68.154.1.107
cd /opt/automacao-relatorios
bash scripts/deploy.sh          # ou: bash scripts/deploy.sh dev
```

O script puxa o codigo, reconstroi a imagem, recria o container, limpa as
imagens orfas e so termina quando o healthcheck passa. Se o container subir
`unhealthy`, ele imprime as ultimas linhas do log e sai com erro.

Ele usa `git merge --ff-only` de proposito: se alguem tiver editado arquivo
direto na VM, o deploy **para** em vez de descartar a alteracao em silencio.

### Atualizacao automatica a cada push

**Opcao A — pipeline chamando a VM (redeploy imediato).** Um workflow que
conecta por SSH e roda o script. Exemplo para GitHub Actions:

```yaml
name: deploy
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: appleboy/ssh-action@v1
        with:
          host: 68.154.1.107
          username: inovacao
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: cd /opt/automacao-relatorios && bash scripts/deploy.sh main
```

Gere um par de chaves dedicado ao deploy, coloque a publica em
`~/.ssh/authorized_keys` na VM e a privada no secret `SSH_PRIVATE_KEY`. No Azure
DevOps o equivalente e uma task `SSH@0` com um Service Connection.

**Opcao B — cron na VM (polling, sem depender de CI).**

```bash
crontab -e
```

```cron
*/5 * * * * cd /opt/automacao-relatorios && DEPLOY_SO_SE_MUDOU=1 bash scripts/deploy.sh main >> /var/log/deploy-relatorios.log 2>&1
```

Com `DEPLOY_SO_SE_MUDOU=1` o script compara o commit local com o remoto e sai
sem fazer nada quando nao ha novidade — o rebuild so acontece quando houve push.

### Comandos uteis na VM

```bash
cd /opt/automacao-relatorios
docker compose ps                 # estado e health
docker compose logs -f            # log ao vivo
docker compose restart            # reiniciar sem rebuild
docker compose down               # parar e remover
docker compose up -d --build      # subir reconstruindo
```

---

## Alternativa: stack no Portainer

**Stacks > Add stack > Repository**

| Campo | Valor |
| --- | --- |
| Name | `automacao-relatorios` |
| Repository URL | URL deste repositorio |
| Repository reference | `refs/heads/main` |
| Compose path | `docker-compose.yml` |
| Skip TLS Verification | desmarcado, salvo Git com certificado interno |

Aqui **nao existe `.env`** (ele nao vai para o repositorio), entao as variaveis
precisam ser cadastradas no bloco **Environment variables** da stack. O mesmo
compose funciona nos dois modos: por SSH ele le o `.env`, no Portainer ele le as
variaveis da stack.

Para redeploy automatico, ligue **GitOps updates** na stack — webhook (o
Portainer gera a URL, voce cadastra no provedor Git) ou polling por intervalo.

## Variaveis de ambiente

| Variavel | Obrigatoria | Padrao |
| --- | --- | --- |
| `AZURE_OPENAI_API_KEY` | sim | — |
| `AZURE_OPENAI_BASE_URL` | nao | `https://wheaton-openai.services.ai.azure.com/openai/v1` |
| `AZURE_OPENAI_DEPLOYMENT` | nao | `gpt-4.1-mini` |
| `APP_PORT` | nao | `8501` |

Sem `AZURE_OPENAI_API_KEY` o deploy falha na hora, com a mensagem da propria
variavel — de proposito, para nao subir um container que so quebraria no momento
de gerar o relatorio.

## Validacao

1. `http://68.154.1.107:8501` abre a tela "Relatorio Diario da Producao".
2. `docker compose ps` mostra o container **healthy** (o healthcheck bate em
   `/_stcore/health` a cada 30s, com 45s de carencia na subida).
3. Suba os dois Excel e gere um relatorio: se o PDF sair **com os graficos**, o
   Chromium esta funcionando.

## Particularidades desta solucao

**Chromium na imagem.** O `kaleido` 1.x nao embute mais o navegador: ele usa um
Chromium do sistema para converter os graficos Plotly em PNG. Por isso o
Dockerfile instala `chromium` e `fonts-liberation`, e define `BROWSER_PATH`.
Isso deixa a imagem em ~1,4 GB.

Se o Chromium faltar, `utils/graficos.py` engole a excecao e o relatorio sai
**sem os graficos, sem nenhum erro na tela** — entao a validacao do PDF acima
nao e opcional.

**Sem volume.** O app nao persiste nada: os uploads vivem na sessao do Streamlit
e o PDF e devolvido pelo `st.download_button`. Recriar o container nao perde
dado nenhum.

**Sem dados de producao na imagem.** O `.dockerignore` exclui `analytics/data/`,
que contem planilhas reais de producao.

**Timezone.** O container roda em `America/Sao_Paulo`, para o "Gerado em
dd/mm/aaaa as HH:MM" do rodape do PDF bater com o horario da fabrica.

## Problemas comuns

| Sintoma | Causa provavel |
| --- | --- |
| Deploy falha citando `AZURE_OPENAI_API_KEY` | `.env` ausente/incompleto na VM, ou variavel nao cadastrada na stack |
| `scripts/deploy.sh` para no `git merge --ff-only` | alguem editou arquivo direto na VM; resolva no Git antes |
| App sobe mas nao abre de fora | porta `8501` fechada no NSG da VM no Azure |
| PDF sai sem graficos | Chromium ausente ou quebrado na imagem |
| Container fica `unhealthy` | Streamlit nao subiu; ver `docker compose logs` |
| `permission denied` no `docker` | falta `usermod -aG docker` e reabrir a sessao SSH |
| Push nao atualiza o container | pipeline/cron nao configurado (a VM nao se atualiza sozinha) |

## Rodando local

```bash
cp .env.example .env   # preencha AZURE_OPENAI_API_KEY
docker compose up --build -d
```

Acesse `http://localhost:8501`.
