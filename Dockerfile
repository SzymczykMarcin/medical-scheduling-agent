FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

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

RUN useradd --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /tmp/medical-scheduling-agent \
    && chown -R app:app /app /tmp/medical-scheduling-agent

ENV BACKEND_HOST=0.0.0.0
ENV BACKEND_PORT=8080
ENV RAG_DOCUMENT_DIR=/app/data/rag
ENV CHROMA_PERSIST_DIR=/tmp/medical-scheduling-agent/chroma
ENV SQLITE_DATABASE_URL=sqlite:////tmp/medical-scheduling-agent/demo.sqlite3

USER app

CMD ["sh", "-c", "uvicorn app.main:app --host ${BACKEND_HOST:-0.0.0.0} --port ${PORT:-8080}"]
