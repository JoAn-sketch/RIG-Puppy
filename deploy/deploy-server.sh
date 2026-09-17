#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR="${RIG_PUPPY_REPO_DIR:-/home/ubuntu/RIG-Puppy}"
RUNTIME_DIR="${RIG_PUPPY_RUNTIME_DIR:-/home/ubuntu/rig-puppy-runtime}"
COMPOSE_FILE="$REPO_DIR/deploy/docker-compose.server.yml"
SERVER_DIR="$REPO_DIR/xiaozhi-esp32-server-main"

cd "$REPO_DIR"
test -d .git
test -f "$COMPOSE_FILE"
test -f "$SERVER_DIR/Dockerfile-server"
test -f "$RUNTIME_DIR/server.env"
test -f "$RUNTIME_DIR/data/.config.yaml"
test -d "$RUNTIME_DIR/models/SenseVoiceSmall"

git fetch origin main
git checkout main
git pull --ff-only origin main

export COMPOSE_FILE
set -a
source "$RUNTIME_DIR/server.env"
set +a

docker compose --env-file "$RUNTIME_DIR/server.env" -f "$COMPOSE_FILE" config >/tmp/rig-puppy-compose-check.yml
COMMIT="$(git rev-parse --short=12 HEAD)"
IMAGE="rig-puppy-server:$COMMIT"

docker build -f "$SERVER_DIR/Dockerfile-server" -t "$IMAGE" "$SERVER_DIR"
docker tag "$IMAGE" rig-puppy-server:main
docker compose --env-file "$RUNTIME_DIR/server.env" -f "$COMPOSE_FILE" up -d --no-deps --force-recreate xiaozhi-esp32-server

docker ps --format '{{.Names}}|{{.Status}}' | grep '^xiaozhi-esp32-server|'
curl --fail --max-time 10 http://127.0.0.1:8003/xiaozhi/ota/ >/dev/null
echo "deployed_commit=$COMMIT"
echo "deployed_image=$IMAGE"
