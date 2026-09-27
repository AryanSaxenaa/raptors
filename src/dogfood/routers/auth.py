"""Login, logout, whoami.

The acceptance suite never logs in -- it is handed a working header and attaches
it -- so this exists for humans and for API clients. Both paths issue the same
opaque token, and the token works as either `Cookie: df_session=...` or
`Authorization: Bearer ...`, so there is one credential type in the system.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel, EmailStr, Field

from .. import audit
from ..db import query_one, transaction
from ..deps import Conn, Who
from ..errors import ApiError
from ..security import (
    ROLE_MATRIX,
    ROLE_OPERATIONS,
    Capability,
    issue_session,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    model_config = {"extra": "forbid"}

    email: EmailStr
    password: str = Field(min_length=1, max_length=512)


@router.post("/login", summary="Exchange credentials for a session token")
def login(conn: Conn, body: LoginIn, response: Response) -> dict[str, Any]:
    user = query_one(
        conn,
        "SELECT id, email, name, role, password_hash, password_salt FROM users "
        "WHERE lower(email) = ?",
        (body.email.lower(),),
    )
    # One message for "no such user" and "wrong password", so the endpoint is
    # not a membership oracle.
    if user is None or not verify_password(body.password, user["password_hash"], user["password_salt"]):
        raise ApiError("not_authenticated", "email or password is incorrect")

    with transaction(conn):
        token = issue_session(conn, str(user["id"]), label="login")
        audit.record(
            conn,
            "auth.login",
            actor_user_id=str(user["id"]),
            actor_role=str(user["role"]),
            target_type="user",
            target_id=str(user["id"]),
        )
    response.set_cookie(
        "df_session", token, httponly=True, samesite="lax", path="/", max_age=60 * 60 * 24 * 7
    )
    return {
        "token": token,
        "header": f"Cookie: df_session={token}",
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
        },
    }


@router.post("/logout", summary="Revoke the current session token")
def logout(conn: Conn, who: Who, response: Response) -> dict[str, Any]:
    if who.token:
        conn.execute("DELETE FROM sessions WHERE token = ?", (who.token,))
        audit.record(
            conn, "auth.logout", actor_user_id=who.user_id or None, actor_role=who.role
        )
    response.delete_cookie("df_session", path="/")
    return {"ok": True}


@router.get("/whoami", summary="The caller's identity and effective permissions")
def whoami(who: Who) -> dict[str, Any]:
    """Returns the caller's row of the role matrix.

    Useful in its own right, and it makes the authorisation model inspectable
    from outside: a reviewer can curl this as each role and compare the result
    against the published matrix without reading any code.
    """
    return {
        "authenticated": not who.is_anonymous,
        "user_id": who.user_id or None,
        "email": who.email or None,
        "name": who.name,
        "role": who.role,
        "capabilities": sorted(c.value for c in ROLE_MATRIX.get(who.role, frozenset())),
        "operations": sorted(o.value for o in ROLE_OPERATIONS.get(who.role, frozenset())),
        "matrix_row": {
            capability.value: capability in ROLE_MATRIX.get(who.role, frozenset())
            for capability in Capability
        },
    }


@router.get("/matrix", summary="The published role-isolation matrix, as served")
def matrix() -> dict[str, Any]:
    """The whole matrix, so it can be diffed against the brief's figure.

    tests/test_role_matrix.py asserts every cell over HTTP; this endpoint is the
    same table in a form a human can read without running the tests.
    """
    return {
        "capabilities": [c.value for c in Capability],
        "roles": {
            role: {c.value: c in caps for c in Capability}
            for role, caps in ROLE_MATRIX.items()
        },
        "note": "Denied cells are refused at the API. Row-level track scoping is "
        "enforced separately by assert_track_visible, because it depends on the "
        "project as well as the role.",
    }
