# Build from the REPOSITORY ROOT so the shared/ package is available:
#   docker build -f backend/user-service/Dockerfile -t data260-g1-user-service .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv/service:/srv \
    USER_SERVICE_PORT=8101

WORKDIR /srv
COPY backend/user-service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared /srv/shared
COPY backend/user-service /srv/service
WORKDIR /srv/service

EXPOSE 8101
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${USER_SERVICE_PORT}"]
