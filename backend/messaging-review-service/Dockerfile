# Build from the REPOSITORY ROOT so the shared/ package is available:
#   docker build -f backend/messaging-review-service/Dockerfile -t data260-g1-messaging-review-service .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv/service:/srv \
    MESSAGING_REVIEW_SERVICE_PORT=8131

WORKDIR /srv
COPY backend/messaging-review-service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared /srv/shared
COPY backend/messaging-review-service /srv/service
WORKDIR /srv/service

EXPOSE 8131
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${MESSAGING_REVIEW_SERVICE_PORT}"]
