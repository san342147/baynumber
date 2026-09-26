from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .auth import authenticate, make_session, read_session
from .config import Settings
from .db import DatabaseMissing
from .models import AssignmentCreate, BayCreate, LoginRequest, MovementCreate
from .service import Conflict, Ledger, NotFound


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({"level": record.levelname, "event": record.getMessage()}, separators=(",", ":"))


logger = logging.getLogger("baynumber")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    ledger = Ledger(config.db_path)
    app = FastAPI(title="BayNumber", version="0.1.0")
    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.exception_handler(DatabaseMissing)
    async def missing_database(_request: Request, exc: DatabaseMissing) -> PlainTextResponse:
        logger.error("database_missing")
        return PlainTextResponse(str(exc), status_code=503)

    @app.exception_handler(Conflict)
    async def conflict(_request: Request, exc: Conflict) -> PlainTextResponse:
        logger.warning("conflict")
        return PlainTextResponse(str(exc), status_code=409)

    @app.exception_handler(NotFound)
    async def not_found(_request: Request, exc: NotFound) -> PlainTextResponse:
        return PlainTextResponse(str(exc), status_code=404)

    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_error(_request: Request, _exc: sqlite3.IntegrityError) -> PlainTextResponse:
        logger.warning("database_constraint")
        return PlainTextResponse("Database constraint rejected this action", status_code=409)

    def current_user(request: Request) -> dict[str, Any]:
        user = read_session(config, request.cookies.get("baynumber_session"))
        if user is None:
            raise HTTPException(status_code=401, detail="Sign in to view the private board")
        return user

    def writer(request: Request, x_csrf_token: str | None = Header(default=None), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if not x_csrf_token or x_csrf_token != user["csrf"]:
            raise HTTPException(status_code=403, detail="Missing or invalid CSRF token")
        return user

    def admin(user: dict[str, Any] = Depends(writer)) -> dict[str, Any]:
        if user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        return user

    def admin_read(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        return user

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(static / "index.html")

    @app.post("/api/login")
    def login(item: LoginRequest, response: Response) -> dict[str, str]:
        role = authenticate(config, item.username, item.password)
        if role is None:
            logger.warning("login_failed")
            raise HTTPException(status_code=401, detail="Invalid username or password")
        token, csrf = make_session(config, item.username, role)
        response.set_cookie("baynumber_session", token, httponly=True, secure=config.secure_cookie, samesite="strict", max_age=8 * 3600)
        logger.info("login_success role=%s", role)
        return {"username": item.username, "role": role, "csrf": csrf}

    @app.post("/api/logout")
    def logout(response: Response, _user: dict[str, Any] = Depends(writer)) -> dict[str, bool]:
        response.delete_cookie("baynumber_session", samesite="strict")
        return {"ok": True}

    @app.get("/api/me")
    def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, str]:
        return {"username": user["user"], "role": user["role"], "csrf": user["csrf"]}

    @app.get("/api/board")
    def board(_user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
        return ledger.board()

    @app.get("/api/lookup")
    def lookup(plate: str, _user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        try:
            return ledger.lookup(plate)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/demo-board")
    def demo_board() -> list[dict[str, Any]]:
        return [
            {"id": 1, "label": "A-04", "state": "occupied", "unit": None, "plate": None, "assignment_id": 1},
            {"id": 2, "label": "A-05", "state": "assigned", "unit": None, "plate": None, "assignment_id": 2},
            {"id": 3, "label": "B-01", "state": "free", "unit": None, "plate": None, "assignment_id": None},
            {"id": 4, "label": "B-02", "state": "conflict", "unit": None, "plate": None, "assignment_id": 3},
        ]

    @app.post("/api/bays", status_code=201)
    def create_bay(item: BayCreate, user: dict[str, Any] = Depends(admin)) -> dict[str, Any]:
        logger.info("bay_created actor=%s", user["user"])
        return ledger.create_bay(item)

    @app.post("/api/assignments", status_code=201)
    def assign(item: AssignmentCreate, user: dict[str, Any] = Depends(admin)) -> dict[str, Any]:
        result = ledger.assign(item, user["user"])
        logger.info("assignment_created id=%s actor=%s", result["id"], user["user"])
        return result

    @app.post("/api/assignments/{assignment_id}/end")
    def end_assignment(assignment_id: int, user: dict[str, Any] = Depends(admin)) -> dict[str, Any]:
        result = ledger.end_assignment(assignment_id, user["user"])
        logger.info("assignment_ended id=%s actor=%s", assignment_id, user["user"])
        return result

    @app.post("/api/movements", status_code=201)
    def move(item: MovementCreate, user: dict[str, Any] = Depends(writer)) -> dict[str, Any]:
        result = ledger.move(item, user["user"])
        logger.info("movement_recorded id=%s kind=%s actor=%s", result["id"], item.kind, user["user"])
        return result

    @app.get("/api/export/{kind}.csv")
    def export(kind: str, _user: dict[str, Any] = Depends(admin_read)) -> PlainTextResponse:
        if kind not in ("events", "assignment-audit"):
            raise HTTPException(status_code=404, detail="Export not found")
        return PlainTextResponse(ledger.export_csv(kind), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="baynumber-{kind}.csv"'})

    return app
