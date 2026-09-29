"""Outbound webhooks for audit events (T4).

Audit writes enqueue rows only; a background worker performs HTTP delivery so
request handlers never block on remote endpoints.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from .db import connect, query, query_one, transaction, utcnow

DEFAULT_TIMEOUT = 2.0
BATCH_SIZE = 10
MAX_ATTEMPTS = 5


def sign_body(secret: str, raw: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()


def _matches(actions_json: str, action: str) -> bool:
    try:
        actions = json.loads(actions_json or '["*"]')
    except json.JSONDecodeError:
        actions = ["*"]
    if not isinstance(actions, list):
        return False
    return "*" in actions or action in actions


def enqueue_for_audit(
    conn: sqlite3.Connection,
    *,
    event_id: str | None,
    action: str,
    payload: dict[str, Any],
) -> None:
    """Append one outbox row (fast, same transaction as audit)."""
    try:
        out_id = f"whx_{secrets.token_hex(6)}"
        conn.execute(
            """
            INSERT INTO webhook_outbox (id, event_id, action, payload, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                out_id,
                event_id,
                action,
                json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
                utcnow(),
            ),
        )
    except Exception:
        return


def _deliver_one(
    conn: sqlite3.Connection,
    *,
    webhook_id: str,
    outbox_id: str | None,
    url: str,
    secret: str,
    action: str,
    event_id: str | None,
    payload: dict[str, Any],
    attempt: int = 1,
) -> tuple[bool, int | None, str | None]:
    body = {
        "action": action,
        "event_id": event_id,
        "payload": payload,
        "sent_at": utcnow(),
    }
    raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    signature = sign_body(secret, raw)
    delivery_id = f"whd_{secrets.token_hex(6)}"
    status_code: int | None = None
    success = 0
    error: str | None = None
    try:
        response = httpx.post(
            url,
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Dogfood-Signature": f"sha256={signature}",
                "X-Dogfood-Event": action,
            },
            timeout=DEFAULT_TIMEOUT,
        )
        status_code = response.status_code
        success = 1 if 200 <= response.status_code < 300 else 0
        if not success:
            error = (response.text or "")[:500]
    except httpx.HTTPError as exc:
        error = str(exc)[:500]
    conn.execute(
        """
        INSERT INTO webhook_deliveries (id, webhook_id, outbox_id, action, status_code, success,
                                        attempt, error, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (delivery_id, webhook_id, outbox_id, action, status_code, success, attempt, error, utcnow()),
    )
    return bool(success), status_code, error


def _next_try_at(attempts: int) -> str:
    delay = min(2 ** max(attempts, 1), 300)
    return (datetime.now(timezone.utc) + timedelta(seconds=delay)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def process_outbox_batch(conn: sqlite3.Connection, *, limit: int = BATCH_SIZE) -> int:
    """Deliver pending outbox rows. Returns count processed (success or given-up)."""
    now = utcnow()
    pending = query(
        conn,
        """
        SELECT id, event_id, action, payload, attempts FROM webhook_outbox
         WHERE processed_at IS NULL
           AND (next_try_at IS NULL OR next_try_at <= ?)
           AND attempts < ?
         ORDER BY created_at ASC LIMIT ?
        """,
        (now, MAX_ATTEMPTS, limit),
    )
    if not pending:
        return 0
    hooks = query(
        conn,
        "SELECT id, event_id, url, secret, actions FROM webhooks WHERE active = 1",
    )
    processed = 0
    for row in pending:
        payload = json.loads(row["payload"] or "{}")
        action = row["action"]
        event_id = row["event_id"]
        failed = False
        matched = False
        attempt_n = int(row["attempts"] or 0) + 1
        for hook in hooks:
            if hook["event_id"] is not None and hook["event_id"] != event_id:
                continue
            if not _matches(hook["actions"], action):
                continue
            matched = True
            already = query_one(
                conn,
                "SELECT 1 AS ok FROM webhook_deliveries "
                "WHERE outbox_id = ? AND webhook_id = ? AND success = 1",
                (row["id"], hook["id"]),
            )
            if already:
                continue
            success, _, _ = _deliver_one(
                conn,
                webhook_id=hook["id"],
                outbox_id=row["id"],
                url=hook["url"],
                secret=hook["secret"],
                action=action,
                event_id=event_id,
                payload=payload,
                attempt=attempt_n,
            )
            if not success:
                failed = True
        attempts = int(row["attempts"] or 0)
        if not matched:
            conn.execute(
                "UPDATE webhook_outbox SET processed_at = ? WHERE id = ?",
                (now, row["id"]),
            )
            processed += 1
            continue
        if failed:
            attempts += 1
            if attempts >= MAX_ATTEMPTS:
                conn.execute(
                    "UPDATE webhook_outbox SET attempts = ?, processed_at = ? WHERE id = ?",
                    (attempts, now, row["id"]),
                )
            else:
                conn.execute(
                    "UPDATE webhook_outbox SET attempts = ?, next_try_at = ? WHERE id = ?",
                    (attempts, _next_try_at(attempts), row["id"]),
                )
            processed += 1
            continue
        conn.execute(
            "UPDATE webhook_outbox SET processed_at = ?, attempts = ? WHERE id = ?",
            (now, attempts, row["id"]),
        )
        processed += 1
    return processed


_worker_stop: threading.Event | None = None
_worker_thread: threading.Thread | None = None


def start_outbox_worker(db_path: Path) -> None:
    global _worker_stop, _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _worker_stop = threading.Event()

    def loop() -> None:
        assert _worker_stop is not None
        while not _worker_stop.is_set():
            conn = connect(db_path)
            try:
                with transaction(conn):
                    process_outbox_batch(conn)
            except Exception:
                pass
            finally:
                conn.close()
            _worker_stop.wait(0.25)

    _worker_thread = threading.Thread(target=loop, name="webhook-outbox", daemon=True)
    _worker_thread.start()


def stop_outbox_worker() -> None:
    global _worker_stop, _worker_thread
    if _worker_stop:
        _worker_stop.set()
    if _worker_thread:
        _worker_thread.join(timeout=2.0)
    _worker_stop = None
    _worker_thread = None


def flush_outbox(conn: sqlite3.Connection) -> int:
    """Process all pending rows (tests and manual test hook)."""
    total = 0
    while True:
        with transaction(conn):
            n = process_outbox_batch(conn, limit=BATCH_SIZE)
        total += n
        if n == 0:
            break
    return total
