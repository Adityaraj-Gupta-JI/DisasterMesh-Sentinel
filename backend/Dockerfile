# NOT VERIFIED: docker is unavailable on the development machine.
FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir \
    "fastapi==0.115.*" "uvicorn[standard]==0.32.*" "sqlalchemy==2.0.*" \
    "pydantic==2.*" "cryptography==43.*"

COPY protocol /app/protocol
COPY backend /app/backend

ENV PYTHONPATH=/app/protocol:/app/backend
WORKDIR /app/backend

# Never run as root: a gateway holding incident data is a target.
RUN useradd --uid 10001 --no-create-home sentinel && mkdir -p /data && chown sentinel /data
USER sentinel

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
