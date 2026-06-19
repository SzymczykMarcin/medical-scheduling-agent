FROM ollama/ollama:0.23.4 AS ollama-runtime

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_ROOT_USER_ACTION=ignore
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
ENV NVIDIA_SITE_PACKAGES=/opt/venv/lib/python3.12/site-packages/nvidia
ENV LD_LIBRARY_PATH="${NVIDIA_SITE_PACKAGES}/cublas/lib:${NVIDIA_SITE_PACKAGES}/cuda_runtime/lib:${NVIDIA_SITE_PACKAGES}/cudnn/lib:${LD_LIBRARY_PATH}"
ENV OLLAMA_HOST=127.0.0.1:11434
ENV OLLAMA_MODELS=/models
ENV OLLAMA_KEEP_ALIVE=0

ARG BIELIK_OLLAMA_MODEL=SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0
ARG EMBEDDING_OLLAMA_MODEL=embeddinggemma:latest

WORKDIR /app

COPY --from=ollama-runtime /bin/ollama /usr/local/bin/ollama

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake ffmpeg libgomp1 \
    && python -m venv "${VIRTUAL_ENV}" \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml /app/backend/pyproject.toml
COPY backend/app /app/backend/app
COPY data/rag /app/data/rag
COPY data/samples/.gitkeep /app/data/samples/.gitkeep

WORKDIR /app/backend

RUN python -m pip install --upgrade pip \
    && python -m pip install ".[cloud]"

RUN set -eux; \
    mkdir -p "${OLLAMA_MODELS}"; \
    ollama serve & \
    server_pid="$!"; \
    sleep 5; \
    ollama pull "${BIELIK_OLLAMA_MODEL}"; \
    ollama pull "${EMBEDDING_OLLAMA_MODEL}"; \
    kill "${server_pid}" || true

COPY deploy/cloud-run/backend-entrypoint.sh /app/backend-entrypoint.sh

RUN useradd --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /tmp/medical-scheduling-agent \
    && chmod +x /app/backend-entrypoint.sh \
    && chown -R app:app /app /tmp/medical-scheduling-agent "${OLLAMA_MODELS}"

ENV BACKEND_HOST=0.0.0.0
ENV BACKEND_PORT=8080
ENV RAG_DOCUMENT_DIR=/app/data/rag
ENV CHROMA_PERSIST_DIR=/tmp/medical-scheduling-agent/chroma
ENV SQLITE_DATABASE_URL=sqlite:////tmp/medical-scheduling-agent/demo.sqlite3

USER app

CMD ["sh", "/app/backend-entrypoint.sh"]
