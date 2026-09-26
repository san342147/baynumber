from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from .config import Settings


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def authenticate(settings: Settings, username: str, password: str) -> str | None:
    for role, user, expected in (
        ("admin", settings.admin_user, settings.admin_password),
        ("guard", settings.guard_user, settings.guard_password),
    ):
        if hmac.compare_digest(username, user) and hmac.compare_digest(password, expected):
            return role
    return None


def make_session(settings: Settings, username: str, role: str) -> tuple[str, str]:
    csrf = secrets.token_urlsafe(24)
    payload = {"user": username, "role": role, "csrf": csrf, "exp": int(time.time()) + 8 * 3600}
    body = _encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = _encode(hmac.new(settings.session_secret.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{signature}", csrf


def read_session(settings: Settings, token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        body, signature = token.split(".", 1)
        expected = _encode(hmac.new(settings.session_secret.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(_decode(body))
        if payload["exp"] < time.time() or payload["role"] not in ("guard", "admin"):
            return None
        return payload
    except (ValueError, KeyError, TypeError):
        return None
