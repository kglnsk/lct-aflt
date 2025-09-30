from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import get_config
from .base import Base

_ENGINE = None
SessionLocal: sessionmaker[Session] | None = None


def get_engine():
    global _ENGINE
    if _ENGINE is None:
        config = get_config()
        database_url = config.database_url
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        _ENGINE = create_engine(database_url, future=True, echo=False, connect_args=connect_args)
    return _ENGINE


def get_session_factory() -> sessionmaker[Session]:
    global SessionLocal
    if SessionLocal is None:
        SessionLocal = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False, class_=Session)
    return SessionLocal


def init_db() -> None:
    """Create database tables if they don't exist."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    factory = get_session_factory()
    db = factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db() -> Generator[Session, None, None]:
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()

