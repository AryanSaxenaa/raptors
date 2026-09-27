"""Fixed-window rate limiting, backed by the same SQLite file as everything else.

Deliberately not in-memory: a limiter that resets when the process restarts is
not a limiter, and an attacker who can trigger a restart gets a fresh budget.
Fixed windows are coarser than a sliding log but need one row per bucket and no
background sweep, which suits a single-node self-hosted portal.
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone

from fastapi import Request

from .errors import ApiError


def client_fingerprint(request: Request, salt: str = "dogfood") -> str:
    """A stable, non-reversible handle for an unauthenticated client.

    Hashed rather than stored raw: an audit log an organizer can read should
    not also be a list of visitor IP addresses.
    """
    client = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    source = forwarded or client
    return hashlib.sha256(f"{salt}:{source}".encode()).hexdigest()[:32]


def check(
    conn: sqlite3.Connection,
    bucket: str,
    *,
    limit: int,
    window_seconds: int,
) -> None:
    """Consume one unit from `bucket`, or raise 429."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=window_seconds)
    row = conn.execute(
        "SELECT window_start, count FROM rate_limits WHERE bucket = ?", (bucket,)
    ).fetchone()

    if row is None or (row["window_start"] or "") < window_start.strftime("%Y-%m-%dT%H:%M:%SZ"):
        conn.execute(
            "INSERT INTO rate_limits (bucket, window_start, count) VALUES (?, ?, 1) "
            "ON CONFLICT (bucket) DO UPDATE SET window_start = excluded.window_start, count = 1",
            (bucket, now.strftime("%Y-%m-%dT%H:%M:%SZ")),
        )
        return

    if int(row["count"]) >= limit:
        raise ApiError(
            "rate_limited",
            f"limit of {limit} requests per {window_seconds}s reached for this bucket",
            extra={"limit": limit, "window_seconds": window_seconds},
        )
    conn.execute("UPDATE rate_limits SET count = count + 1 WHERE bucket = ?", (bucket,))
