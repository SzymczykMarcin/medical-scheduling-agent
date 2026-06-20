#!/bin/sh
set -eu

export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export OLLAMA_MODELS="${OLLAMA_MODELS:-/models}"
export OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:--1}"
export OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL:-1}"
export OLLAMA_DEBUG="${OLLAMA_DEBUG:-1}"
export OLLAMA_LIBRARY_PATH="${OLLAMA_LIBRARY_PATH:-/usr/lib/ollama}"

PYTHON_SITE_PACKAGES="$(python - <<'PY'
import site

paths = site.getsitepackages()
if not paths:
    raise SystemExit("No Python site-packages paths found.")
print(paths[0])
PY
)"

export NVIDIA_SITE_PACKAGES="${NVIDIA_SITE_PACKAGES:-${PYTHON_SITE_PACKAGES}/nvidia}"
PYTHON_CUDA_LIBRARY_PATH="${NVIDIA_SITE_PACKAGES}/cublas/lib:${NVIDIA_SITE_PACKAGES}/cuda_runtime/lib:${NVIDIA_SITE_PACKAGES}/cudnn/lib"
ORIGINAL_LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"

log_startup_diagnostics() {
  echo "[startup] Backend container diagnostics"
  echo "[startup] OLLAMA_HOST=${OLLAMA_HOST}"
  echo "[startup] OLLAMA_MODELS=${OLLAMA_MODELS}"
  echo "[startup] OLLAMA_KEEP_ALIVE=${OLLAMA_KEEP_ALIVE:-<unset>}"
  echo "[startup] OLLAMA_NUM_PARALLEL=${OLLAMA_NUM_PARALLEL:-<unset>}"
  echo "[startup] OLLAMA_DEBUG=${OLLAMA_DEBUG:-<unset>}"
  echo "[startup] OLLAMA_LLM_LIBRARY=${OLLAMA_LLM_LIBRARY:-<unset/autodetect>}"
  echo "[startup] OLLAMA_LIBRARY_PATH=${OLLAMA_LIBRARY_PATH:-<unset>}"
  echo "[startup] PYTHON_SITE_PACKAGES=${PYTHON_SITE_PACKAGES}"
  echo "[startup] NVIDIA_SITE_PACKAGES=${NVIDIA_SITE_PACKAGES}"
  echo "[startup] ORIGINAL_LD_LIBRARY_PATH=${ORIGINAL_LD_LIBRARY_PATH:-<unset>}"
  echo "[startup] PYTHON_CUDA_LIBRARY_PATH=${PYTHON_CUDA_LIBRARY_PATH}"
  echo "[startup] CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-<unset>}"
  echo "[startup] NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-<unset>}"

  if command -v nvidia-smi >/dev/null 2>&1; then
    echo "[startup] nvidia-smi output:"
    nvidia-smi || true
  else
    echo "[startup] nvidia-smi is not available in this container."
  fi

  echo "[startup] Ollama runtime libraries:"
  if [ -d "${OLLAMA_LIBRARY_PATH}" ]; then
    find "${OLLAMA_LIBRARY_PATH}" -maxdepth 2 -type f | sort | sed -n '1,120p'
  else
    echo "[startup] Missing Ollama library directory: ${OLLAMA_LIBRARY_PATH}" >&2
  fi

  echo "[startup] Python CUDA runtime libraries:"
  if [ -d "${NVIDIA_SITE_PACKAGES}" ]; then
    find "${NVIDIA_SITE_PACKAGES}" -type f \
      \( -name 'libcublas.so*' -o -name 'libcudart.so*' -o -name 'libcudnn.so*' \) \
      | sort | sed -n '1,80p'
  else
    echo "[startup] Missing NVIDIA_SITE_PACKAGES directory: ${NVIDIA_SITE_PACKAGES}" >&2
  fi
}

log_startup_diagnostics

env \
  -u OLLAMA_LLM_LIBRARY \
  OLLAMA_HOST="${OLLAMA_HOST}" \
  OLLAMA_MODELS="${OLLAMA_MODELS}" \
  OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE}" \
  OLLAMA_NUM_PARALLEL="${OLLAMA_NUM_PARALLEL}" \
  OLLAMA_DEBUG="${OLLAMA_DEBUG}" \
  PATH="${PATH}" \
  HOME="${HOME:-/home/app}" \
  NVIDIA_VISIBLE_DEVICES="${NVIDIA_VISIBLE_DEVICES:-all}" \
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

export LD_LIBRARY_PATH="${PYTHON_CUDA_LIBRARY_PATH}:${ORIGINAL_LD_LIBRARY_PATH}"

uvicorn app.main:app \
  --host "${BACKEND_HOST:-0.0.0.0}" \
  --port "${PORT:-8080}"
