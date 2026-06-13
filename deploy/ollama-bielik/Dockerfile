FROM ollama/ollama:0.23.4

ARG MODEL=SpeakLeash/bielik-4.5b-v3.0-instruct:Q8_0

ENV OLLAMA_HOST=0.0.0.0:11434
ENV OLLAMA_MODELS=/models
ENV OLLAMA_DEBUG=false
ENV OLLAMA_KEEP_ALIVE=-1
ENV MODEL=${MODEL}

RUN ollama serve & sleep 5 && ollama pull "${MODEL}"

COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT ["sh", "/entrypoint.sh"]
