from __future__ import annotations

import csv
import io
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from baynumber.db import connect, migrate
from baynumber.models import AssignmentCreate, BayCreate, MovementCreate
from baynumber.service import Conflict, Ledger
from baynumber.web import create_app
from tests.conftest import login


def test_clean_workflow_and_exports(client: TestClient) -> None:
    headers = login(client)
    bay = client.post("/api/bays", json={"label": "A-04"}, headers=headers)
    assert bay.status_code == 201
    bay_id = bay.json()["id"]
    assignment = client.post("/api/assignments", json={"bay_id": bay_id, "unit": "A / 402", "plate": "KA-03 AB 1234"}, headers=headers)
    assert assignment.status_code == 201
    assert assignment.json()["plate"] == "KA03AB1234"
    assert client.get("/api/lookup?plate=ka03ab1234").json()["state"] == "assigned"
    assert client.post("/api/movements", json={"bay_id": bay_id, "kind": "IN"}, headers=headers).status_code == 201
    assert client.get("/api/board").json()[0]["state"] == "occupied"
    assert client.post("/api/movements", json={"bay_id": bay_id, "kind": "OUT"}, headers=headers).status_code == 201
    assert client.post(f"/api/assignments/{assignment.json()['id']}/end", headers=headers).status_code == 200
    events = list(csv.reader(io.StringIO(client.get("/api/export/events.csv").text)))
    assert events[0] == ["event_id", "bay_label", "unit", "plate", "kind", "occurred_at_utc", "recorded_at_utc", "actor"]
    assert [row[4] for row in events[1:]] == ["IN", "OUT"]
    audit = list(csv.reader(io.StringIO(client.get("/api/export/assignment-audit.csv").text)))
    assert audit[0] == ["audit_id", "assignment_id", "action", "occurred_at_utc", "actor", "bay_label", "unit", "plate"]
    assert [row[2] for row in audit[1:]] == ["CREATE", "END"]


def test_concurrent_in_has_one_winner(settings) -> None:
    migrate(settings.db_path)
    ledger = Ledger(settings.db_path)
    bay = ledger.create_bay(BayCreate(label="B-01"))
    ledger.assign(AssignmentCreate(bay_id=bay["id"], unit="B-9", plate="BH12AA1234"), "secretary")
    gate = Barrier(2)

    def attempt() -> str:
        gate.wait()
        try:
            ledger.move(MovementCreate(bay_id=bay["id"], kind="IN"), "guard")
            return "success"
        except Conflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(results) == ["conflict", "success"]
    with connect(settings.db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM movements").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("DELETE FROM movements")


def test_constraints_and_assignment_transaction(settings) -> None:
    migrate(settings.db_path)
    ledger = Ledger(settings.db_path)
    first = ledger.create_bay(BayCreate(label="A-04"))
    second = ledger.create_bay(BayCreate(label="A-05"))
    with pytest.raises(Conflict, match="already exists"):
        ledger.create_bay(BayCreate(label="A-04"))
    assignment = ledger.assign(AssignmentCreate(bay_id=first["id"], unit="A-1", plate="KA03AB1234"), "secretary")
    with pytest.raises(Conflict, match="active bay"):
        ledger.assign(AssignmentCreate(bay_id=second["id"], unit="A-2", plate="KA03AB1234"), "secretary")
    ledger.move(MovementCreate(bay_id=first["id"], kind="IN"), "guard")
    with pytest.raises(Conflict, match="occupied"):
        ledger.end_assignment(assignment["id"], "secretary")
    with connect(settings.db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM assignment_audit").fetchone()[0] == 1
        assert db.execute("SELECT ends_at FROM assignments WHERE id=?", (assignment["id"],)).fetchone()[0] is None


def test_validation_permissions_and_missing_database(client: TestClient, settings) -> None:
    assert client.get("/api/board").status_code == 401
    assert client.get("/api/export/events.csv").status_code == 401
    headers = login(client, "guard")
    assert client.get("/api/export/events.csv").status_code == 403
    assert client.post("/api/bays", json={"label": "A-01"}, headers=headers).status_code == 403
    assert client.post("/api/movements", json={"bay_id": 1, "kind": "IN"}).status_code == 403
    client.post("/api/logout", headers=headers)
    admin_headers = login(client)
    assert client.post("/api/bays", json={"label": "A?"}, headers=admin_headers).status_code == 422
    assert client.post("/api/assignments", json={"bay_id": 1, "unit": "A-1", "plate": "!!!"}, headers=admin_headers).status_code == 422
    assert client.get("/api/lookup?plate=!!!").status_code == 422
    missing = TestClient(create_app(settings.__class__(settings.db_path.parent / "missing.db", settings.session_secret, settings.admin_user, settings.admin_password, settings.guard_user, settings.guard_password)))
    missing_headers = login(missing)
    response = missing.get("/api/board")
    assert response.status_code == 503
    assert "init-db" in response.text


def test_public_demo_is_synthetic_and_no_private_board(client: TestClient) -> None:
    response = client.get("/api/demo-board")
    assert response.status_code == 200
    assert all(item["plate"] is None or item["plate"].startswith("DEMO") for item in response.json())
    assert client.get("/api/board").status_code == 401
