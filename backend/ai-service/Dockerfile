# Build from the REPOSITORY ROOT so the shared/ package is available:
#   docker build -f backend/ai-service/Dockerfile -t data260-g1-ai-service .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv/service:/srv \
    AI_SERVICE_PORT=8141

WORKDIR /srv
COPY backend/ai-service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared /srv/shared
COPY backend/ai-service /srv/service
WORKDIR /srv/service

EXPOSE 8141
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${AI_SERVICE_PORT}"]
