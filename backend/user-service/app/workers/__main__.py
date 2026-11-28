"""Run the user-service consumers:  (from backend/user-service, repo root on PYTHONPATH)

    PYTHONPATH=.:../.. ../../.venv/bin/python -m app.workers

Starts two consumer groups in one process:
  user-counters      property.saved, property.unsaved, booking.approved -> guest counters
  user-host-metrics  message.sent -> host response_rate / response_time_minutes
Stop with Ctrl+C.
"""
import logging
import signal
import threading

from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database.connection import get_mysql_engine
from app.workers.handlers import (
    COUNTERS_GROUP, COUNTERS_TOPICS, HOST_METRICS_GROUP, HOST_METRICS_TOPICS, make_handler,
)
from shared.kafka.consumer import run_consumer


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    factory = sessionmaker(bind=get_mysql_engine(), expire_on_commit=False)
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())

    threads = [
        threading.Thread(target=run_consumer, name=group, daemon=True, args=(topics, group, make_handler(factory, group)),
                         kwargs={"bootstrap_servers": settings.kafka_bootstrap_servers,
                                 "client_id": f"user-service-{group}", "stop_event": stop})
        for group, topics in ((COUNTERS_GROUP, COUNTERS_TOPICS), (HOST_METRICS_GROUP, HOST_METRICS_TOPICS))
    ]
    for t in threads:
        t.start()
    logging.getLogger("user_service.workers").info("consumers started: %s", [t.name for t in threads])
    while not stop.is_set() and any(t.is_alive() for t in threads):
        stop.wait(1)
    stop.set()
    for t in threads:
        t.join(timeout=10)


if __name__ == "__main__":
    main()
