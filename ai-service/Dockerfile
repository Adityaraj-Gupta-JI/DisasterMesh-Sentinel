# NOT VERIFIED: docker is unavailable on the development machine.
# Mock mode by default — no model weights are downloaded at build time.
FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir \
    "fastapi==0.115.*" "uvicorn[standard]==0.32.*" "pydantic==2.*" "cryptography==43.*"

COPY protocol /app/protocol
COPY ai-service /app/ai-service

ENV PYTHONPATH=/app/protocol:/app/ai-service
ENV DMS_AI_MODE=mock
WORKDIR /app/ai-service

RUN useradd --uid 10002 --no-create-home aiservice
USER aiservice

EXPOSE 8001
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
