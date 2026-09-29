"""SQLite access.

There is no ORM. Queries are SQL, the schema is schema.sql, and the only thing
this module adds is connection setup, a transaction helper and row access by
column name.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import PACKAGE_DIR, SCHEMA_VERSION, settings

SCHEMA_PATH = PACKAGE_DIR / "schema.sql"


def utcnow() -> str:
    """Current time as ISO-8601 UTC with a Z suffix, matching fixtures.json."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp from the fixtures or the database.

    Always returns an aware datetime in UTC, so callers can compare against
    datetime.now(timezone.utc) without thinking about it. Naive input is
    treated as UTC, which is what both fixtures.json and this schema store.
    Empty input is "no deadline". Invalid input is also None so *read* paths
    stay total; write paths must call require_iso_ts so garbage cannot disable
    a deadline by accident.
    """
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def require_iso_ts(value: str | None, field: str) -> datetime | None:
    """Reject unparseable timestamps on write so they cannot mean 'open forever'."""
    from .errors import ApiError

    if value is None or not str(value).strip():
        return None
    parsed = parse_ts(value)
    if parsed is None:
        raise ApiError("invalid_request", f"{field} is not a valid ISO-8601 timestamp")
    return parsed


def connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path else settings.db_path
    if str(db_path) != ":memory:":
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL keeps the single writer from blocking gallery reads; foreign_keys is
    # off by default in SQLite and every cascade in schema.sql depends on it.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Additive alters for databases created before SCHEMA_VERSION 2.

    CREATE TABLE IF NOT EXISTS will not add columns to an existing table.
    """
    event_cols = _table_columns(conn, "events")
    if "voting_access" not in event_cols:
        conn.execute(
            "ALTER TABLE events ADD COLUMN voting_access TEXT NOT NULL "
            "DEFAULT 'authenticated'"
        )
    outbox_cols = _table_columns(conn, "webhook_outbox")
    if "attempts" not in outbox_cols:
        conn.execute(
            "ALTER TABLE webhook_outbox ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0"
        )
    if "next_try_at" not in outbox_cols:
        conn.execute("ALTER TABLE webhook_outbox ADD COLUMN next_try_at TEXT")


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    apply_migrations(conn)
    conn.execute(
        "INSERT INTO schema_meta (key, value) VALUES ('version', ?) "
        "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        (SCHEMA_VERSION,),
    )


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run a block in one transaction, rolling back on any exception.

    isolation_level=None means sqlite3 does not open transactions implicitly,
    so BEGIN/COMMIT here are the real boundaries.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def query(conn: sqlite3.Connection, sql: str, params: Any = ()) -> list[sqlite3.Row]:
    return conn.execute(sql, params).fetchall()


def query_one(conn: sqlite3.Connection, sql: str, params: Any = ()) -> sqlite3.Row | None:
    return conn.execute(sql, params).fetchone()


def scalar(conn: sqlite3.Connection, sql: str, params: Any = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    return None if row is None else row[0]


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]
