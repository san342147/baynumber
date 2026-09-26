from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from .config import Settings
from .db import migrate
from .models import AssignmentCreate, BayCreate, MovementCreate
from .service import Ledger
from .web import create_app


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def demo_path(settings: Settings) -> Path:
    path = Path(os.getenv("BAYNUMBER_DEMO_DB", "data/demo.db")).resolve()
    if path == settings.db_path.resolve():
        raise RuntimeError("Demo database must differ from the real database")
    return path


def seed_demo(path: Path) -> None:
    migrate(path)
    ledger = Ledger(path)
    for label in ("A-04", "A-05", "A-06", "B-01", "B-02", "C-11"):
        ledger.create_bay(BayCreate(label=label))
    ledger.assign(AssignmentCreate(bay_id=1, unit="DEMO-12", plate="DEMO1234"), "demo-seed")
    ledger.assign(AssignmentCreate(bay_id=2, unit="DEMO-18", plate="DEMO5678"), "demo-seed")
    ledger.assign(AssignmentCreate(bay_id=5, unit="DEMO-21", plate="DEMO9012"), "demo-seed")
    ledger.move(MovementCreate(bay_id=1, kind="IN"), "demo-seed")
    path.with_name(path.name + ".demo-marker").write_text("BayNumber synthetic demo database\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(prog="baynumber")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="Create or migrate the real database")
    sub.add_parser("demo-seed", help="Create a separate synthetic demo database")
    sub.add_parser("demo-reset", help="Delete the marked synthetic demo database")
    serve = sub.add_parser("serve", help="Run the local web app")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    load_dotenv()
    settings = Settings.from_env()
    if args.command == "init-db":
        migrate(settings.db_path)
        print(f"Migrated database: {settings.db_path}")
    elif args.command == "demo-seed":
        path = demo_path(settings)
        if path.exists():
            raise RuntimeError("Demo database already exists; run demo-reset first")
        seed_demo(path)
        print(f"Seeded synthetic demo database: {path}")
    elif args.command == "demo-reset":
        path = demo_path(settings)
        marker = path.with_name(path.name + ".demo-marker")
        if not marker.is_file() or marker.read_text(encoding="utf-8") != "BayNumber synthetic demo database\n":
            raise RuntimeError("Refusing reset: demo marker is missing or invalid")
        for suffix in ("", "-wal", "-shm"):
            target = Path(str(path) + suffix)
            if target.exists():
                target.unlink()
        marker.unlink()
        print(f"Reset synthetic demo database: {path}")
    elif args.command == "serve":
        uvicorn.run(create_app(settings), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
