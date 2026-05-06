"""FastAPI dependency injection."""
from sqlalchemy.orm import Session
from ubid.storage.postgres import get_db as _get_db
from contextlib import contextmanager


def get_db():
    with _get_db() as session:
        yield session
