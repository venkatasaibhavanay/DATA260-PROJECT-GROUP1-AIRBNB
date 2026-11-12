"""Lazy connection factories. Nothing connects until a function is called."""
from functools import lru_cache

from app.config import settings


@lru_cache
def get_mysql_engine():
    from sqlalchemy import create_engine

    return create_engine(settings.mysql_url, pool_pre_ping=True, future=True)


@lru_cache
def get_mongo_db():
    from pymongo import MongoClient

    client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=3000)
    return client[settings.mongo_database]


@lru_cache
def get_redis():
    import redis

    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password or None,
        decode_responses=True,
    )
