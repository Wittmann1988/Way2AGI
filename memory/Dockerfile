FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi>=0.115 \
    uvicorn>=0.34 \
    httpx>=0.27 \
    numpy>=1.26 \
    elias-memory>=0.1 \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-grpc \
    opentelemetry-instrumentation-fastapi \
    redis[hiredis] \
    chromadb-client

COPY src/ ./src/

EXPOSE 8001

CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8001"]
