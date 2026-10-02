# Playbook: subir uma aplicacao na VM com Docker

Roteiro generico para publicar uma aplicacao na VM, com redeploy automatico a
cada push. Serve para qualquer stack (Node, Python, estatico) — o que muda e o
`Dockerfile`.

O padrao e sempre o mesmo: **um repositorio Git com `Dockerfile` +
`docker-compose.yml` na raiz.** A partir dai, dois caminhos que usam exatamente
os mesmos arquivos:

| | SSH | Portainer |
| --- | --- | --- |
| Como chega o codigo | `git clone` na VM | o Portainer clona sozinho |
| Onde ficam os segredos | `.env` na VM | Environment variables da stack |
| Redeploy | `deploy.sh` via SSH | botao *Update the stack* |
| Automacao no push | pipeline por SSH, ou cron | GitOps updates (webhook/polling) |
| Bom quando | quer script, log e CI/CD | quer UI e visao geral das stacks |

Da para ter os dois no mesmo repositorio sem conflito.

---

## 1. O que precisa estar no repositorio

### `Dockerfile`

Pontos que costumam ser esquecidos:

- **Imagem base fixa** (`python:3.13-slim-bookworm`, `node:22-alpine`), nunca
  `:latest` — senao o build muda sozinho entre um deploy e outro.
- **Dependencias antes do codigo**: copie o `requirements.txt` / `package.json`,
  instale, e so depois `COPY . .`. Assim o cache do Docker so e invalidado
  quando as dependencias mudam, e o redeploy de uma mudanca de codigo leva
  segundos em vez de minutos.
- **Usuario nao-root** (`useradd` / `USER`), com `HOME` definido e gravavel.
- **`EXPOSE`** da porta interna da aplicacao.
- **`HEALTHCHECK`** batendo em um endpoint real — e o que permite um deploy
  script (ou o Portainer) dizer *healthy* em vez de so *running*.
- **Bibliotecas de sistema**: se o runtime precisa de binario externo (navegador
  headless para gerar imagem/PDF, `ffmpeg`, driver de banco), instale via
  `apt-get` na imagem. Essa e a causa classica de "funciona local, falha no
  container" — e as vezes falha **em silencio**, quando a aplicacao trata a
  excecao e segue sem o recurso.

### `docker-compose.yml`

```yaml
services:
  minha-app:
    build:
      context: .
      dockerfile: Dockerfile
    image: minha-app:latest
    container_name: minha-app
    pull_policy: build          # reconstroi a imagem a cada redeploy
    restart: unless-stopped
    ports:
      - "${APP_PORT:-3000}:3000"
    environment:
      SEGREDO: ${SEGREDO:?informe SEGREDO no .env ou nas variaveis da stack}
      OPCIONAL: ${OPCIONAL:-valor-padrao}
      TZ: America/Sao_Paulo
    logging:                     # a VM e compartilhada
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

| Item | Por que |
| --- | --- |
| `pull_policy: build` | sem isso o redeploy reusa a imagem antiga e o codigo novo nao sobe |
| `restart: unless-stopped` | o container volta sozinho depois de reboot da VM |
| `${VAR}` | funciona nos dois modos: le o `.env` por SSH, le as variaveis da stack no Portainer |
| `${VAR:?mensagem}` | falha o deploy na hora se faltar segredo, em vez de subir quebrado |
| `${VAR:-padrao}` | valor padrao para o que nao e segredo |
| `logging` | sem limite, o log de um container enche o disco da VM |
| `TZ` | datas geradas pela aplicacao batem com o horario local |

**Nao use `env_file: .env`.** No Portainer o `.env` nem existe (esta no
`.gitignore`), e por SSH o compose ja le o `.env` da pasta automaticamente. Com
`${VAR}` o mesmo arquivo serve para os dois.

**Volume**: so declare se a aplicacao realmente persiste arquivo em disco
(uploads, sqlite). Se o estado vive em memoria ou em banco externo, nao declare
nada — recriar o container fica trivial.

### `.dockerignore`

Tao importante quanto o `Dockerfile`. Sem ele o `COPY . .` leva lixo e, pior,
**segredos e dados reais** para dentro da imagem. Minimo:

```
venv/
node_modules/
__pycache__/
.git/
.env
.env.*
!.env.example
outputs/
(pastas com dados de producao)
```

### `scripts/deploy.sh` (para o caminho SSH)

Um script que faz o ciclo inteiro e **falha alto** quando algo da errado:

```bash
set -euo pipefail
git fetch --prune origin
git merge --ff-only "origin/$BRANCH"    # para se a VM divergiu, em vez de descartar
docker compose up -d --build --remove-orphans
docker image prune -f
# esperar o healthcheck; se unhealthy, imprimir log e sair com erro
```

Detalhes que valem a pena:

- **`--ff-only`**: se alguem editou arquivo direto na VM, o deploy para em vez de
  apagar a alteracao sem avisar.
- **esperar o healthcheck**: sem isso o script termina "com sucesso" enquanto o
  container morre dois segundos depois.
- **`docker image prune -f`**: a cada rebuild fica uma imagem orfa; sem isso o
  disco da VM enche em poucas semanas.
- **checar o `.env` antes de comecar**: erro claro em vez de erro do compose.

---

## 2A. Caminho SSH

### Primeira vez

```bash
ssh usuario@IP_DA_VM

docker --version || curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"     # saia e entre de novo na sessao

sudo mkdir -p /opt/minha-app
sudo chown "$USER":"$USER" /opt/minha-app
git clone URL_DO_REPOSITORIO /opt/minha-app
cd /opt/minha-app

cp .env.example .env
nano .env
chmod 600 .env

docker compose up -d --build
```

Libere a porta no **Network Security Group da VM** (no Azure), senao o app sobe
mas ninguem acessa de fora.

### Atualizacao automatica no push

**Opcao A — pipeline chamando a VM (imediato).**

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
          host: ${{ secrets.VM_HOST }}
          username: ${{ secrets.VM_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: cd /opt/minha-app && bash scripts/deploy.sh main
```

Gere um par de chaves **dedicado ao deploy**: a publica em
`~/.ssh/authorized_keys` na VM, a privada no secret. No Azure DevOps, a task
`SSH@0` com um Service Connection faz o mesmo.

**Opcao B — cron na VM (polling, sem CI).**

```cron
*/5 * * * * cd /opt/minha-app && DEPLOY_SO_SE_MUDOU=1 bash scripts/deploy.sh main >> /var/log/deploy-minha-app.log 2>&1
```

Use quando nao houver CI, ou quando o runner nao alcanca a VM pela rede.

---

## 2B. Caminho Portainer

**Stacks > Add stack > Repository**

| Campo | Valor |
| --- | --- |
| Name | nome da stack (vira prefixo dos recursos) |
| Repository URL | URL do repositorio Git |
| Repository reference | `refs/heads/main` (vazio = branch padrao) |
| Compose path | `docker-compose.yml` |
| Skip TLS Verification | desmarcado, salvo Git com certificado interno |
| Authentication | ligue se o repositorio for privado |

Em **Environment variables**, cadastre tudo que o compose le com `${...}`. Esse e
o lugar onde credenciais vivem: nunca no `docker-compose.yml`, nunca commitadas.

### Atualizacao automatica no push

Ligue **GitOps updates** e escolha:

- **Webhook**: o Portainer gera uma URL (`.../api/stacks/webhooks/<uuid>`);
  cadastre no provedor Git como webhook de push (GitHub: *Settings > Webhooks*,
  content type `application/json`, *Just the push event*; Azure DevOps: *Project
  Settings > Service Hooks > Web Hooks > Code pushed*; GitLab: *Settings >
  Webhooks > Push events*). Redeploy em segundos.
- **Polling**: o Portainer consulta o repositorio num intervalo e redeploya
  quando o commit muda. **Use se a VM nao for alcancavel pela internet** — um
  webhook de provedor na nuvem nunca chega num Portainer interno.

Sem nenhum dos dois, o container segue rodando a versao do ultimo deploy manual.

---

## 3. Checklist antes de dar deploy

- [ ] `Dockerfile`, `docker-compose.yml` e `.dockerignore` na raiz e commitados
- [ ] `docker compose config` roda sem erro
- [ ] `docker build .` passa localmente
- [ ] container roda e responde no endpoint de health
- [ ] a funcionalidade que depende de binario de sistema foi testada **dentro do
      container**, nao so no ambiente local
- [ ] nenhum segredo no compose; todos como `${VAR}`
- [ ] `.dockerignore` exclui `.env` e pastas de dados reais
- [ ] `.env` criado na VM (SSH) ou variaveis cadastradas na stack (Portainer)
- [ ] porta liberada no NSG da VM
- [ ] automacao de redeploy configurada (pipeline, cron ou GitOps updates)

---

## 4. Diagnostico rapido

| Sintoma | Onde olhar |
| --- | --- |
| Deploy falha citando uma variavel | `.env` ausente na VM, ou faltou cadastrar em *Environment variables* |
| Push nao atualiza o container | automacao nao configurada; ou webhook nao alcanca a VM (troque por polling) |
| Redeploy roda mas o codigo e o antigo | falta `pull_policy: build`, ou `--build` no `compose up` |
| `deploy.sh` para no `merge --ff-only` | alguem editou arquivo direto na VM; resolva no Git antes |
| Container reinicia em loop | `docker compose logs`: quase sempre variavel faltando ou porta em uso |
| `unhealthy` mas a app abre | o `HEALTHCHECK` aponta para endpoint/porta errada |
| App sobe mas nao abre de fora | porta fechada no NSG da VM |
| `permission denied` no `docker` | falta `usermod -aG docker` e reabrir a sessao SSH |
| Funciona local, falha no container | dependencia de sistema que existe na sua maquina e nao na imagem |
| Porta ja em uso | outra stack usa a mesma porta na VM; mude o `APP_PORT` |
| Disco da VM enchendo | faltou `docker image prune` no deploy, ou `logging` sem limite |
| Imagem gigante / build lento | `.dockerignore` incompleto, ou dependencias copiadas depois do codigo |

---

## 5. Fluxo do dia a dia

1. Alterar o codigo e commitar na branch da stack.
2. Push.
3. A automacao redeploya — ou, manualmente:
   - SSH: `cd /opt/minha-app && bash scripts/deploy.sh`
   - Portainer: *Update the stack*, com *Re-pull image and redeploy* marcado.
4. Conferir o container *healthy* e validar na URL.
