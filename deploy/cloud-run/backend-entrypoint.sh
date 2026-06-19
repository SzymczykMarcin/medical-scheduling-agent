#!/bin/sh
set -eu

export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export OLLAMA_MODELS="${OLLAMA_MODELS:-/models}"

ollama serve &
ollama_pid="$!"

cleanup() {
  kill "${ollama_pid}" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

until ollama list >/dev/null 2>&1; do
  if ! kill -0 "${ollama_pid}" 2>/dev/null; then
    echo "Ollama server failed to start." >&2
    exit 1
  fi
  sleep 1
done

if [ "${PULL_MODELS_ON_START:-0}" = "1" ]; then
  ollama pull "${OLLAMA_MODEL:-SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0}"
  ollama pull "${EMBEDDING_MODEL_NAME:-embeddinggemma:latest}"
fi

uvicorn app.main:app \
  --host "${BACKEND_HOST:-0.0.0.0}" \
  --port "${PORT:-8080}"
