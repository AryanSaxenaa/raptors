"""Seeded development sessions (DOGFOOD_DEV_TOKENS)."""

from __future__ import annotations

from fastapi import Response

from .db import query_one

DEV_LOGIN_LABELS = frozenset({"organizer", "judge_a", "judge_b", "participant", "admin"})

_SESSION_COOKIE = "df_session"
_SESSION_MAX_AGE = 60 * 60 * 24 * 7


def lookup_dev_session(conn, label: str):
    key = label.strip()
    if key not in DEV_LOGIN_LABELS:
        return None
    return query_one(
        conn,
        """
        SELECT s.token, u.id, u.email, u.name, u.role
          FROM sessions s JOIN users u ON u.id = s.user_id
         WHERE s.label = ?
        """,
        (key,),
    )


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        _SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=_SESSION_MAX_AGE,
    )
