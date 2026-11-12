# Build from the REPOSITORY ROOT so the shared/ package is available:
#   docker build -f backend/analytics-service/Dockerfile -t data260-g1-analytics-service .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv/service:/srv \
    ANALYTICS_SERVICE_PORT=8151

WORKDIR /srv
COPY backend/analytics-service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared /srv/shared
COPY backend/analytics-service /srv/service
WORKDIR /srv/service

EXPOSE 8151
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${ANALYTICS_SERVICE_PORT}"]
