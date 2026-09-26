from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from baynumber.config import Settings
from baynumber.db import migrate
from baynumber.web import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(tmp_path / "ledger.db", "s" * 40, "secretary", "admin-password-123", "guard", "guard-password-123")


@pytest.fixture
def client(settings: Settings) -> TestClient:
    migrate(settings.db_path)
    return TestClient(create_app(settings))


def login(client: TestClient, role: str = "admin") -> dict[str, str]:
    data = ("secretary", "admin-password-123") if role == "admin" else ("guard", "guard-password-123")
    response = client.post("/api/login", json={"username": data[0], "password": data[1]})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf"]}
