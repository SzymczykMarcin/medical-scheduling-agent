FROM ollama/ollama:0.23.4

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_ROOT_USER_ACTION=ignore
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
ENV OLLAMA_LIBRARY_PATH=/usr/lib/ollama
ENV OLLAMA_HOST=127.0.0.1:11434
ENV OLLAMA_MODELS=/models
ENV OLLAMA_KEEP_ALIVE=-1

ARG BIELIK_OLLAMA_MODEL=SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0
ARG EMBEDDING_OLLAMA_MODEL=embeddinggemma:latest

WORKDIR /app

RUN set -eux; \
    if ! command -v apt-get >/dev/null 2>&1; then \
        echo "Unsupported ollama base image: apt-get is required to install Python backend dependencies." >&2; \
        exit 1; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        cmake \
        ffmpeg \
        libgomp1 \
        python3 \
        python3-pip \
        python3-venv; \
    python3 -m venv "${VIRTUAL_ENV}"; \
    rm -rf /var/lib/apt/lists/*

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

ENTRYPOINT []
CMD ["sh", "/app/backend-entrypoint.sh"]
