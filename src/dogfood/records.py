"""Hash-anchored public records (judge participation, project certificates).

Issued once per subject so the hash is stable. Anyone can fetch
GET /api/records/{record_hash} and recompute sha256(head || canonical_json).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from . import audit
from .db import query_one, utcnow


def issue(
    conn: sqlite3.Connection,
    *,
    kind: str,
    subject_id: str,
    event_id: str | None,
    body: dict[str, Any],
) -> dict[str, Any]:
    existing = query_one(
        conn,
        "SELECT payload FROM issued_records WHERE kind = ? AND subject_id = ?",
        (kind, subject_id),
    )
    if existing:
        return json.loads(existing["payload"])

    chain = audit.verify_chain(conn)
    issued_at = utcnow()
    payload = {
        **body,
        "kind": kind,
        "issued_at": issued_at,
        "audit_chain_head": chain.get("head_hash"),
        "audit_chain_ok": chain.get("ok"),
    }
    record_hash = audit._entry_hash(  # noqa: SLF001 — same canonical form as the log
        chain.get("head_hash") or audit.GENESIS_HASH, payload
    )
    payload["record_hash"] = record_hash
    conn.execute(
        """
        INSERT INTO issued_records (record_hash, kind, subject_id, event_id, payload, issued_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            record_hash,
            kind,
            subject_id,
            event_id,
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            issued_at,
        ),
    )
    return payload


def get_by_hash(conn: sqlite3.Connection, record_hash: str) -> dict[str, Any] | None:
    row = query_one(
        conn, "SELECT payload FROM issued_records WHERE record_hash = ?", (record_hash,)
    )
    if row is None:
        return None
    return json.loads(row["payload"])


def verify_payload(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    stored_hash = payload.get("record_hash")
    if not isinstance(stored_hash, str):
        return {"ok": False, "reason": "missing record_hash"}
    head = payload.get("audit_chain_head") or audit.GENESIS_HASH
    body = {k: v for k, v in payload.items() if k != "record_hash"}
    expected = audit._entry_hash(str(head), body)  # noqa: SLF001
    ok = expected == stored_hash
    stored = get_by_hash(conn, stored_hash)
    return {
        "ok": ok and stored is not None,
        "expected_hash": expected,
        "provided_hash": stored_hash,
        "on_file": stored is not None,
    }
