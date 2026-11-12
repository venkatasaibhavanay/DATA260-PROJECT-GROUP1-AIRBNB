# Build from the REPOSITORY ROOT so the shared/ package is available:
#   docker build -f backend/booking-service/Dockerfile -t data260-g1-booking-service .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv/service:/srv \
    BOOKING_SERVICE_PORT=8121

WORKDIR /srv
COPY backend/booking-service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY shared /srv/shared
COPY backend/booking-service /srv/service
WORKDIR /srv/service

EXPOSE 8121
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${BOOKING_SERVICE_PORT}"]
