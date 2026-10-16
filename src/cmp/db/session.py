from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from cmp.config import get_settings
from cmp.db.models import Base

_engine = None
_Session: sessionmaker[Session] | None = None


def engine():  # type: ignore[no-untyped-def]
    global _engine, _Session
    if _engine is None:
        _engine = create_engine(get_settings().database_url, future=True)
        Base.metadata.create_all(_engine)  # replace with alembic once schema stabilises
        _Session = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


@contextmanager
def session() -> Iterator[Session]:
    engine()
    assert _Session is not None
    s = _Session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
