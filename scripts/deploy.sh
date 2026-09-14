#!/usr/bin/env bash
#
# Atualiza a aplicacao na VM: puxa o codigo mais recente do Git e recria o
# container com a imagem reconstruida.
#
# Uso na VM:
#   cd /opt/automacao-relatorios
#   bash scripts/deploy.sh            # branch main
#   bash scripts/deploy.sh dev        # outra branch
#
# Com DEPLOY_SO_SE_MUDOU=1 o script sai sem fazer nada quando o commit local ja
# e o mesmo do remoto — e o modo usado pelo cron de atualizacao automatica.
set -euo pipefail

BRANCH="${1:-main}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$RAIZ"

if [ ! -f .env ]; then
  echo "ERRO: .env nao encontrado em $RAIZ" >&2
  echo "Crie a partir do .env.example e preencha AZURE_OPENAI_API_KEY." >&2
  exit 1
fi

echo ">> Atualizando o codigo (branch $BRANCH)"
git fetch --prune origin

if [ "${DEPLOY_SO_SE_MUDOU:-0}" = "1" ]; then
  if [ "$(git rev-parse HEAD)" = "$(git rev-parse "origin/$BRANCH")" ]; then
    echo ">> Nada novo em origin/$BRANCH, nada a fazer."
    exit 0
  fi
fi

git checkout "$BRANCH"
# --ff-only de proposito: se a copia da VM divergiu do remoto, o deploy para
# aqui em vez de descartar alteracao sem avisar.
git merge --ff-only "origin/$BRANCH"

echo ">> Commit em uso: $(git rev-parse --short HEAD) - $(git log -1 --pretty=%s)"

echo ">> Reconstruindo e subindo o container"
docker compose up -d --build --remove-orphans

echo ">> Removendo imagens orfas do build anterior"
docker image prune -f >/dev/null

echo ">> Aguardando o healthcheck"
for _ in $(seq 1 24); do
  estado="$(docker inspect -f '{{.State.Health.Status}}' automacao-relatorios 2>/dev/null || echo ausente)"
  if [ "$estado" = "healthy" ]; then
    echo ">> Container saudavel"
    docker compose ps
    exit 0
  fi
  if [ "$estado" = "unhealthy" ]; then
    echo "ERRO: container subiu unhealthy. Ultimas linhas do log:" >&2
    docker compose logs --tail 30 >&2
    exit 1
  fi
  sleep 5
done

echo "ERRO: o container nao ficou saudavel em 2 minutos. Ultimas linhas do log:" >&2
docker compose logs --tail 30 >&2
exit 1
