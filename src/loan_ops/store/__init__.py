"""Database access: engine cache, sessions, schema bootstrap (GOALS 1.4)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from loan_ops.config import Settings, get_settings
from loan_ops.db import Base

_engine_cache: dict[str, object] = {}


def get_engine(settings: Settings | None = None):
    settings = settings or get_settings()
    key = settings.db_url
    if key not in _engine_cache:
        if key.startswith("sqlite"):
            _engine_cache[key] = create_engine(key, connect_args={"check_same_thread": False})
        else:
            _engine_cache[key] = create_engine(key)
    return _engine_cache[key]


def create_all(engine=None) -> None:
    """Dev convenience; Alembic migrations are canonical (GOALS 1.4)."""
    engine = engine or get_engine()
    Base.metadata.create_all(engine)


def reset_engine_cache() -> None:
    _engine_cache.clear()


@contextmanager
def session_scope(engine=None) -> Iterator[Session]:
    engine = engine or get_engine()
    maker = sessionmaker(bind=engine)
    session = maker()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
