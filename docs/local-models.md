# Local Models

## Directory Convention

Place local models outside Git tracking:

```text
models/
  bielik/
    minitron-Bielik-7B-v3.0-Instruct-GGUF.Q4_K_M.gguf
  whisper/
    ...
```

The exact filenames do not matter as long as `.env` points to them.

## Bielik Setup

### llama.cpp provider

This project can reuse the already downloaded GGUF model from the `interactive-cv` project:

```text
C:/009_Firma/safe_space/interactive-cv/models/bielik-minitron-7b-q4/minitron-Bielik-7B-v3.0-Instruct-GGUF.Q4_K_M.gguf
```

Configure:

```env
LLM_PROVIDER=llama-cpp
BIELIK_GGUF_PATH=C:/009_Firma/safe_space/interactive-cv/models/bielik-minitron-7b-q4/minitron-Bielik-7B-v3.0-Instruct-GGUF.Q4_K_M.gguf
LLM_CONTEXT_TOKENS=4096
LLM_GPU_LAYERS=-1
```

The RAG data remains separate for this project. Only the GGUF model file is reused.

### Ollama HTTP provider

Use this mode when Bielik is served by a local or remote Ollama-compatible model server.
The backend will not load GGUF weights into its own process.

```env
LLM_PROVIDER=ollama-http
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0
OLLAMA_TIMEOUT_SECONDS=120
```

The provider calls `POST /api/chat` with `stream: false`.

## Whisper Setup

The default ASR target is:

```env
ASR_PROVIDER=faster-whisper
ASR_MODEL_NAME=large-v3-turbo
ASR_DEVICE=cuda
ASR_COMPUTE_TYPE=int8_float16
```

## Mock Mode

Keep this enabled until models are downloaded and configured:

```env
DEMO_MODE=true
```

Disable it when real inference is ready:

```env
DEMO_MODE=false
```

## References

- Bielik 11B v2 Technical Report: https://arxiv.org/abs/2505.02410
- Bielik 11B v3 Technical Report: https://arxiv.org/abs/2601.11579
- Bielik Minitron 7B report: https://arxiv.org/abs/2603.11881
- OpenAI Whisper repository: https://github.com/openai/whisper
- faster-whisper repository: https://github.com/SYSTRAN/faster-whisper
