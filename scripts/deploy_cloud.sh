#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${AI_CHAT_ROOT:-/workspace/projects/ai-chat}"
FRONTEND_LOG="/tmp/ai-chat-frontend.log"
BACKEND_LOG="/tmp/ai-chat-backend.log"
LOCK_PATCH="/tmp/ai-chat-cloud-package-lock.patch"

cd "$ROOT"

echo "[1/7] Preserving cloud-only lockfile changes"
if ! git diff --quiet -- frontend/package-lock.json; then
  git diff -- frontend/package-lock.json > "$LOCK_PATCH"
  git stash push -m "cloud package-lock before avatar deployment" -- frontend/package-lock.json
fi

echo "[2/7] Pulling the verified revision"
git pull --ff-only
REVISION="$(git rev-parse --short HEAD)"
echo "Revision: $REVISION"

echo "[3/7] Downloading the ModelScope avatar action model"
python backend/scripts/download_avatar_action_model.py

echo "[4/7] Running focused verification"
python -m compileall -q backend
if python -c 'import pytest' >/dev/null 2>&1; then
  python -m pytest backend/tests/test_avatar_director.py -q
fi
(
  cd frontend
  npm test -- --run
  npm run build
)

stop_port() {
  local port="$1"
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" >/dev/null 2>&1 || true
    return
  fi
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -ti tcp:"$port" || true)"
    if [ -n "$pids" ]; then
      kill $pids
    fi
  fi
}

echo "[5/7] Restarting frontend and backend"
stop_port 3090
stop_port 8000

(
  cd "$ROOT/frontend"
  nohup npm run dev -- --host 0.0.0.0 --port 3090 > "$FRONTEND_LOG" 2>&1 &
  echo $! > /tmp/ai-chat-frontend.pid
)

(
  cd "$ROOT/backend"
  nohup python -m uvicorn app:app --host 0.0.0.0 --port 8000 > "$BACKEND_LOG" 2>&1 &
  echo $! > /tmp/ai-chat-backend.pid
)

echo "[6/7] Waiting for services"
frontend_ready=false
backend_ready=false
for _ in $(seq 1 150); do
  if curl -fsS --max-time 2 http://127.0.0.1:3090/ >/dev/null 2>&1; then
    frontend_ready=true
  fi
  if curl -fsS --max-time 2 http://127.0.0.1:8000/health >/dev/null 2>&1; then
    backend_ready=true
  fi
  if [ "$frontend_ready" = true ] && [ "$backend_ready" = true ]; then
    break
  fi
  sleep 2
done

if [ "$frontend_ready" != true ]; then
  echo "Frontend failed to start. Last log lines:"
  tail -n 60 "$FRONTEND_LOG" || true
  exit 1
fi
if [ "$backend_ready" != true ]; then
  echo "Backend failed to start. Last log lines:"
  tail -n 80 "$BACKEND_LOG" || true
  exit 1
fi

echo "[7/7] Verifying live asset and action director"
VERIFY_MODEL="/tmp/lacrimosa-live.verify.glb"
curl -fsS http://127.0.0.1:3090/models/lacrimosa-live.glb -o "$VERIFY_MODEL"
MODEL_BYTES="$(stat -c %s "$VERIFY_MODEL")"
rm -f "$VERIFY_MODEL"

COMPUTE_STATUS="$(curl -fsS http://127.0.0.1:8000/compute-status)"
ACTION_CHECK="$(curl -fsS --max-time 10 \
  -H 'Content-Type: application/json' \
  -d '{"answer":"I am happy to see you.","retrieved_memories":[],"companion_type":"female"}' \
  http://127.0.0.1:8000/avatar/action)"

echo "DEPLOYMENT_OK revision=$REVISION model_bytes=$MODEL_BYTES"
echo "COMPUTE_STATUS=$COMPUTE_STATUS"
echo "ACTION_CHECK=$ACTION_CHECK"
