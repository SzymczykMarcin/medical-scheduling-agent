#!/bin/sh
set -eu

export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export OLLAMA_MODELS="${OLLAMA_MODELS:-/models}"

log_startup_diagnostics() {
  echo "[startup] Backend container diagnostics"
  echo "[startup] OLLAMA_HOST=${OLLAMA_HOST}"
  echo "[startup] OLLAMA_MODELS=${OLLAMA_MODELS}"
  echo "[startup] OLLAMA_LLM_LIBRARY=${OLLAMA_LLM_LIBRARY:-<auto>}"
  echo "[startup] OLLAMA_LIBRARY_PATH=${OLLAMA_LIBRARY_PATH:-<unset>}"
  echo "[startup] LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-<unset>}"
  echo "[startup] CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-<unset>}"
  echo "[startup] NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-<unset>}"

  if command -v nvidia-smi >/dev/null 2>&1; then
    echo "[startup] nvidia-smi output:"
    nvidia-smi || true
  else
    echo "[startup] nvidia-smi is not available in this container."
  fi

  echo "[startup] Ollama runtime libraries:"
  if [ -d "${OLLAMA_LIBRARY_PATH:-/usr/lib/ollama}" ]; then
    find "${OLLAMA_LIBRARY_PATH:-/usr/lib/ollama}" -maxdepth 2 -type f | sort | sed -n '1,80p'
  else
    echo "[startup] Missing Ollama library directory: ${OLLAMA_LIBRARY_PATH:-/usr/lib/ollama}" >&2
  fi

  echo "[startup] Python CUDA runtime libraries:"
  if [ -d "${NVIDIA_SITE_PACKAGES:-/opt/venv/lib/python3.12/site-packages/nvidia}" ]; then
    find "${NVIDIA_SITE_PACKAGES}" -type f \
      \( -name 'libcublas.so*' -o -name 'libcudart.so*' -o -name 'libcudnn.so*' \) \
      | sort | sed -n '1,80p'
  else
    echo "[startup] Missing NVIDIA_SITE_PACKAGES directory: ${NVIDIA_SITE_PACKAGES:-<unset>}" >&2
  fi
}

log_startup_diagnostics

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
