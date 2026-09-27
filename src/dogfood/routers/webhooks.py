"""Webhook subscription management (T4)."""

from __future__ import annotations

import json
import secrets
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field, HttpUrl

from .. import audit
from ..db import query, query_one, transaction, utcnow
from ..deps import Conn, Who, get_event
from ..errors import ApiError
from ..security import Operation, require_operation
from ..webhooks import enqueue_for_audit, flush_outbox

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


class WebhookIn(BaseModel):
    model_config = {"extra": "forbid"}

    url: HttpUrl
    event_id: str | None = Field(default=None, min_length=1, max_length=80)
    actions: list[str] = Field(default_factory=lambda: ["*"], max_length=50)


@router.get("", summary="List webhook subscriptions")
def list_webhooks(conn: Conn, who: Who, event_id: str | None = None) -> dict[str, Any]:
    require_operation(conn, who, Operation.MANAGE_EVENT)
    if event_id:
        get_event(conn, event_id)
        rows = query(
            conn,
            "SELECT id, event_id, url, actions, active, created_at FROM webhooks "
            "WHERE event_id IS NULL OR event_id = ? ORDER BY created_at DESC",
            (event_id,),
        )
    else:
        rows = query(
            conn,
            "SELECT id, event_id, url, actions, active, created_at FROM webhooks "
            "ORDER BY created_at DESC",
        )
    return {
        "webhooks": [
            {
                **dict(r),
                "actions": json.loads(r["actions"] or '["*"]'),
                "active": bool(r["active"]),
            }
            for r in rows
        ]
    }


@router.post("", status_code=201, summary="Register a webhook")
def create_webhook(conn: Conn, who: Who, body: WebhookIn) -> dict[str, Any]:
    require_operation(conn, who, Operation.MANAGE_EVENT)
    if body.event_id:
        get_event(conn, body.event_id)
    hook_id = f"whk_{secrets.token_hex(6)}"
    secret = secrets.token_urlsafe(24)
    actions_json = json.dumps(body.actions or ["*"])
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO webhooks (id, event_id, url, secret, actions, active, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (hook_id, body.event_id, str(body.url), secret, actions_json, utcnow()),
        )
        audit.record(
            conn,
            "webhook.created",
            event_id=body.event_id,
            actor_user_id=who.user_id,
            actor_role=who.role,
            target_type="webhook",
            target_id=hook_id,
            detail={"url": str(body.url), "actions": body.actions},
        )
    return {
        "id": hook_id,
        "url": str(body.url),
        "event_id": body.event_id,
        "actions": body.actions,
        "secret": secret,
        "signing": "HMAC-SHA256 of the raw JSON body in X-Dogfood-Signature: sha256=…",
    }


@router.delete("/{webhook_id}", summary="Disable a webhook")
def delete_webhook(conn: Conn, who: Who, webhook_id: str) -> dict[str, Any]:
    require_operation(conn, who, Operation.MANAGE_EVENT)
    row = query_one(conn, "SELECT * FROM webhooks WHERE id = ?", (webhook_id,))
    if row is None:
        raise ApiError("not_found", f"no webhook '{webhook_id}'")
    with transaction(conn):
        conn.execute("UPDATE webhooks SET active = 0 WHERE id = ?", (webhook_id,))
        audit.record(
            conn,
            "webhook.disabled",
            event_id=row["event_id"],
            actor_user_id=who.user_id,
            actor_role=who.role,
            target_type="webhook",
            target_id=webhook_id,
        )
    return {"id": webhook_id, "active": False}


@router.post("/{webhook_id}/test", summary="Send a test delivery")
def test_webhook(conn: Conn, who: Who, webhook_id: str) -> dict[str, Any]:
    require_operation(conn, who, Operation.MANAGE_EVENT)
    row = query_one(conn, "SELECT * FROM webhooks WHERE id = ?", (webhook_id,))
    if row is None or not row["active"]:
        raise ApiError("not_found", f"no active webhook '{webhook_id}'")
    with transaction(conn):
        enqueue_for_audit(
            conn,
            event_id=row["event_id"],
            action="webhook.test",
            payload={"webhook_id": webhook_id, "message": "dogfood portal test delivery"},
        )
    flush_outbox(conn)
    last = query_one(
        conn,
        "SELECT success, status_code, error FROM webhook_deliveries "
        "WHERE webhook_id = ? ORDER BY created_at DESC LIMIT 1",
        (webhook_id,),
    )
    return {
        "webhook_id": webhook_id,
        "success": bool(last and last["success"]),
        "status_code": last["status_code"] if last else None,
        "error": last["error"] if last else None,
    }
