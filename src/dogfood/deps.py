"""Shared FastAPI dependencies: a connection, and who is asking."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request

from .db import connect, query_one
from .errors import ApiError
from .security import Identity, resolve_identity


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    """One connection per request. Opening a SQLite connection is cheap; sharing
    one across threads is not worth the locking it costs."""
    conn = connect(request.app.state.db_path)
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[sqlite3.Connection, Depends(get_conn)]


def get_identity(request: Request, conn: Conn) -> Identity:
    return resolve_identity(conn, request)


Who = Annotated[Identity, Depends(get_identity)]


def get_event(conn: sqlite3.Connection, event_id: str) -> sqlite3.Row:
    row = query_one(conn, "SELECT * FROM events WHERE id = ?", (event_id,))
    if row is None:
        raise ApiError("not_found", f"no event '{event_id}'")
    return row


def default_event_id(conn: sqlite3.Connection) -> str:
    """The fixture event, when a route does not name one.

    Preferring the fixture event keeps `/projects` and the exports pointed at
    the shared dataset, which is the whole reason for shared fixtures: a judge
    opening two portals should be comparing software, not test data.
    """
    row = query_one(
        conn, "SELECT id FROM events ORDER BY is_fixture DESC, created_at ASC LIMIT 1"
    )
    if row is None:
        raise ApiError("not_found", "no events exist")
    return str(row["id"])
