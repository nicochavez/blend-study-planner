"""LangGraph checkpointer providing Postgres-backed conversation memory.

The chat graph persists its message history per ``thread_id`` through this
checkpointer, so follow-up questions in the same conversation retain context
across requests. Production uses ``PostgresSaver`` (the same database the app
already runs on); tests override ``get_checkpointer`` with an ``InMemorySaver``.
"""

from functools import lru_cache

from langgraph.checkpoint.base import BaseCheckpointSaver

from ...core.config import settings


@lru_cache
def get_checkpointer() -> BaseCheckpointSaver:
    """Return a process-wide PostgresSaver, creating its tables on first use.

    Imported lazily so test suites that override this dependency never need
    psycopg or a running Postgres.
    """
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg_pool import ConnectionPool

    pool = ConnectionPool(
        conninfo=settings.DATABASE_URL,
        max_size=10,
        kwargs={"autocommit": True, "prepare_threshold": 0},
    )
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()  # idempotent: creates checkpoint tables if absent
    return checkpointer
