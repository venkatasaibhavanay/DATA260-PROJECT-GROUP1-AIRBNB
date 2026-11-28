"""Request-scoped SQLAlchemy sessions for MySQL. Tests override get_session."""
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy.orm import Session, sessionmaker

from app.database.connection import get_mysql_engine


@lru_cache
def _factory() -> sessionmaker:
    return sessionmaker(bind=get_mysql_engine(), expire_on_commit=False, future=True)


def get_session() -> Iterator[Session]:
    session = _factory()()
    try:
        yield session
    finally:
        session.close()
