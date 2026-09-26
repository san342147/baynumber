from __future__ import annotations

import csv
import io
import sqlite3
from contextlib import closing
from datetime import timezone
from pathlib import Path
from typing import Any

from .db import connect, transaction
from .models import AssignmentCreate, BayCreate, MovementCreate, clean_plate, utc_now


class Conflict(Exception):
    pass


class NotFound(Exception):
    pass


def _dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


class Ledger:
    def __init__(self, path: Path):
        self.path = path

    def create_bay(self, item: BayCreate) -> dict[str, Any]:
        with closing(connect(self.path)) as db:
            try:
                with transaction(db):
                    cur = db.execute("INSERT INTO bays(label, created_at) VALUES (?,?)", (item.label, utc_now()))
                return {"id": cur.lastrowid, "label": item.label}
            except sqlite3.IntegrityError as exc:
                raise Conflict(f"Bay {item.label} already exists") from exc

    def assign(self, item: AssignmentCreate, actor: str) -> dict[str, Any]:
        with closing(connect(self.path)) as db:
            with transaction(db):
                bay = db.execute("SELECT label FROM bays WHERE id=?", (item.bay_id,)).fetchone()
                if bay is None:
                    raise NotFound("Bay not found")
                if db.execute("SELECT 1 FROM assignments WHERE bay_id=? AND ends_at IS NULL", (item.bay_id,)).fetchone():
                    raise Conflict(f"Bay {bay['label']} already has an active assignment; end it first")
                if db.execute("SELECT 1 FROM assignments WHERE plate=? AND ends_at IS NULL", (item.plate,)).fetchone():
                    raise Conflict(f"Plate {item.plate} already has an active bay")
                now = utc_now()
                cur = db.execute(
                    "INSERT INTO assignments(bay_id,unit,plate,starts_at,created_by) VALUES (?,?,?,?,?)",
                    (item.bay_id, item.unit, item.plate, now, actor),
                )
                db.execute(
                    "INSERT INTO assignment_audit(assignment_id,action,occurred_at,actor,bay_label,unit,plate) VALUES (?,?,?,?,?,?,?)",
                    (cur.lastrowid, "CREATE", now, actor, bay["label"], item.unit, item.plate),
                )
                return {"id": cur.lastrowid, "bay_id": item.bay_id, "unit": item.unit, "plate": item.plate}

    def end_assignment(self, assignment_id: int, actor: str) -> dict[str, Any]:
        with closing(connect(self.path)) as db:
            with transaction(db):
                row = db.execute(
                    "SELECT a.*, b.label FROM assignments a JOIN bays b ON b.id=a.bay_id WHERE a.id=? AND a.ends_at IS NULL",
                    (assignment_id,),
                ).fetchone()
                if row is None:
                    raise NotFound("Active assignment not found")
                latest = db.execute("SELECT kind FROM movements WHERE bay_id=? ORDER BY id DESC LIMIT 1", (row["bay_id"],)).fetchone()
                if latest and latest["kind"] == "IN":
                    raise Conflict(f"Bay {row['label']} is occupied; record OUT before ending its assignment")
                now = utc_now()
                db.execute("UPDATE assignments SET ends_at=?, ended_by=? WHERE id=?", (now, actor, assignment_id))
                db.execute(
                    "INSERT INTO assignment_audit(assignment_id,action,occurred_at,actor,bay_label,unit,plate) VALUES (?,?,?,?,?,?,?)",
                    (assignment_id, "END", now, actor, row["label"], row["unit"], row["plate"]),
                )
                return {"id": assignment_id, "ended_at": now}

    def move(self, item: MovementCreate, actor: str) -> dict[str, Any]:
        with closing(connect(self.path)) as db:
            with transaction(db):
                bay = db.execute("SELECT label FROM bays WHERE id=?", (item.bay_id,)).fetchone()
                if bay is None:
                    raise NotFound("Bay not found")
                assignment = db.execute(
                    "SELECT id, plate FROM assignments WHERE bay_id=? AND ends_at IS NULL", (item.bay_id,)
                ).fetchone()
                if assignment is None:
                    raise Conflict(f"Bay {bay['label']} has no active assignment")
                latest = db.execute("SELECT kind FROM movements WHERE bay_id=? ORDER BY id DESC LIMIT 1", (item.bay_id,)).fetchone()
                occupied = latest is not None and latest["kind"] == "IN"
                if item.kind == "IN" and occupied:
                    raise Conflict(f"Bay {bay['label']} is already occupied; no IN event was recorded")
                if item.kind == "OUT" and not occupied:
                    raise Conflict(f"Bay {bay['label']} is not occupied; no OUT event was recorded")
                occurred = item.occurred_at.astimezone(timezone.utc).isoformat(timespec="seconds") if item.occurred_at else utc_now()
                cur = db.execute(
                    "INSERT INTO movements(bay_id,assignment_id,kind,occurred_at,recorded_at,actor) VALUES (?,?,?,?,?,?)",
                    (item.bay_id, assignment["id"], item.kind, occurred, utc_now(), actor),
                )
                return {"id": cur.lastrowid, "bay_id": item.bay_id, "kind": item.kind, "occurred_at": occurred}

    def board(self) -> list[dict[str, Any]]:
        with closing(connect(self.path)) as db:
            rows = db.execute("""
                SELECT b.id, b.label, a.id AS assignment_id, a.unit, a.plate,
                    (SELECT m.kind FROM movements m WHERE m.bay_id=b.id ORDER BY m.id DESC LIMIT 1) AS last_kind
                FROM bays b LEFT JOIN assignments a ON a.bay_id=b.id AND a.ends_at IS NULL
                ORDER BY b.label
            """).fetchall()
            result = []
            for row in rows:
                item = _dict(row)
                item["state"] = "occupied" if item["last_kind"] == "IN" else "assigned" if item["assignment_id"] else "free"
                result.append(item)
            return result

    def lookup(self, plate: str) -> dict[str, Any]:
        normalized = clean_plate(plate)
        matches = [bay for bay in self.board() if bay["plate"] == normalized]
        if not matches:
            raise NotFound("No active assignment for that plate")
        return matches[0]

    def export_csv(self, kind: str) -> str:
        if kind == "events":
            headers = ["event_id", "bay_label", "unit", "plate", "kind", "occurred_at_utc", "recorded_at_utc", "actor"]
            query = """SELECT m.id, b.label, a.unit, a.plate, m.kind, m.occurred_at, m.recorded_at, m.actor
                FROM movements m JOIN bays b ON b.id=m.bay_id JOIN assignments a ON a.id=m.assignment_id ORDER BY m.id"""
        elif kind == "assignment-audit":
            headers = ["audit_id", "assignment_id", "action", "occurred_at_utc", "actor", "bay_label", "unit", "plate"]
            query = "SELECT id, assignment_id, action, occurred_at, actor, bay_label, unit, plate FROM assignment_audit ORDER BY id"
        else:
            raise ValueError("Unknown export")
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\r\n")
        writer.writerow(headers)
        with closing(connect(self.path)) as db:
            writer.writerows(tuple(row) for row in db.execute(query))
        return output.getvalue()
