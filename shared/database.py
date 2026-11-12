"""Shared SQLAlchemy declarative base for MySQL-backed services."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
