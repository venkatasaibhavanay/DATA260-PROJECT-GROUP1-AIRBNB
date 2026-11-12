# Build from the REPOSITORY ROOT so the shared/ package is available:
#   docker build -f backend/property-service/Dockerfile -t data260-g1-property-service .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv/service:/srv \
    PROPERTY_SERVICE_PORT=8111

WORKDIR /srv
COPY backend/property-service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared /srv/shared
COPY backend/property-service /srv/service
WORKDIR /srv/service

EXPOSE 8111
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PROPERTY_SERVICE_PORT}"]
