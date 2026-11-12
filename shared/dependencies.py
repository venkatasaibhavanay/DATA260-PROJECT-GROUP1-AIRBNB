"""Active connectivity probes for external dependencies.

Used only by GET /health/dependencies. Each probe has a short timeout and never
raises: it returns {"status": "ok" | "down", "detail": "..."}.
"""
from typing import Callable, Iterable

from shared.config import InfraSettings

TIMEOUT_S = 2


def _mysql(s: InfraSettings) -> str:
    import pymysql

    conn = pymysql.connect(
        host=s.mysql_host, port=s.mysql_port, user=s.mysql_user,
        password=s.mysql_password, database=s.mysql_database,
        connect_timeout=TIMEOUT_S, read_timeout=TIMEOUT_S,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT VERSION()")
            return f"MySQL {cur.fetchone()[0]}"
    finally:
        conn.close()


def _mongodb(s: InfraSettings) -> str:
    from pymongo import MongoClient

    client = MongoClient(s.mongo_uri, serverSelectionTimeoutMS=TIMEOUT_S * 1000)
    try:
        client.admin.command("ping")
        return f"MongoDB {client.server_info()['version']}"
    finally:
        client.close()


def _redis(s: InfraSettings) -> str:
    import redis

    r = redis.Redis(host=s.redis_host, port=s.redis_port,
                    password=s.redis_password or None, socket_timeout=TIMEOUT_S)
    try:
        r.ping()
        return f"Redis {r.info('server')['redis_version']}"
    finally:
        r.close()


def _kafka(s: InfraSettings) -> str:
    from kafka import KafkaAdminClient

    admin = KafkaAdminClient(
        bootstrap_servers=s.kafka_bootstrap_servers,
        request_timeout_ms=TIMEOUT_S * 2000,
        api_version_auto_timeout_ms=TIMEOUT_S * 1000,
        client_id="g1-health-probe",
    )
    try:
        return f"Kafka reachable, {len(admin.list_topics())} topics"
    finally:
        admin.close()


PROBES: dict[str, Callable[[InfraSettings], str]] = {
    "mysql": _mysql,
    "mongodb": _mongodb,
    "redis": _redis,
    "kafka": _kafka,
}


def check_dependencies(settings: InfraSettings, names: Iterable[str]) -> dict[str, dict]:
    results: dict[str, dict] = {}
    for name in names:
        probe = PROBES.get(name)
        if probe is None:
            results[name] = {"status": "down", "detail": "unknown dependency"}
            continue
        try:
            results[name] = {"status": "ok", "detail": probe(settings)}
        except Exception as exc:  # noqa: BLE001 - report, never crash the endpoint
            results[name] = {"status": "down", "detail": f"{type(exc).__name__}: {exc}"[:300]}
    return results
