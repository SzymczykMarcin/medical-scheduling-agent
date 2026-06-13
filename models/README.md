# Local Model Files

Do not commit local model weights to this repository.

Suggested layout:

```text
models/
  bielik/
    bielik-11b-v3-instruct-q4_k_m.gguf
  whisper/
    ...
```

The backend reads model locations from `.env`.
