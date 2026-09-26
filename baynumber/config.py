from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path
    session_secret: str
    admin_user: str
    admin_password: str
    guard_user: str
    guard_password: str
    secure_cookie: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        secret = os.getenv("BAYNUMBER_SESSION_SECRET", "")
        admin_password = os.getenv("BAYNUMBER_ADMIN_PASSWORD", "")
        guard_password = os.getenv("BAYNUMBER_GUARD_PASSWORD", "")
        if (len(secret) < 32 or len(admin_password) < 12 or len(guard_password) < 12
                or any(value.startswith("replace-with-") for value in (secret, admin_password, guard_password))
                or admin_password == guard_password):
            raise RuntimeError("Set BAYNUMBER_SESSION_SECRET (32+ chars) and both passwords (12+ chars) in environment")
        return cls(
            db_path=Path(os.getenv("BAYNUMBER_DB", "data/baynumber.db")),
            session_secret=secret,
            admin_user=os.getenv("BAYNUMBER_ADMIN_USER", "secretary"),
            admin_password=admin_password,
            guard_user=os.getenv("BAYNUMBER_GUARD_USER", "guard"),
            guard_password=guard_password,
            secure_cookie=os.getenv("BAYNUMBER_SECURE_COOKIE", "false").lower() == "true",
        )
