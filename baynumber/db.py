from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class DatabaseMissing(Exception):
    pass


def connect(path: Path, *, create: bool = False) -> sqlite3.Connection:
    if not create and not path.is_file():
        raise DatabaseMissing(f"Database missing at {path}. Run 'baynumber init-db' first.")
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    mode = "rwc" if create else "rw"
    try:
        db = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode={mode}", uri=True, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db
    except sqlite3.OperationalError as exc:
        raise DatabaseMissing(f"Cannot open database at {path}: {exc}") from exc


@contextmanager
def transaction(db: sqlite3.Connection) -> Iterator[None]:
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        db.rollback()
        raise
    else:
        db.commit()


def migrate(path: Path) -> None:
    db = connect(path, create=True)
    try:
        db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)")
        migration_dir = Path(__file__).resolve().parent / "migrations"
        for sql_path in sorted(migration_dir.glob("*.sql")):
            if db.execute("SELECT 1 FROM schema_migrations WHERE version=?", (sql_path.name,)).fetchone():
                continue
            # executescript commits implicitly. Each migration is wrapped in its own script transaction.
            script = "BEGIN IMMEDIATE;\n" + sql_path.read_text(encoding="utf-8") + \
                f"\nINSERT INTO schema_migrations(version) VALUES ('{sql_path.name}');\nCOMMIT;"
            try:
                db.executescript(script)
            except Exception:
                db.rollback()
                raise
    finally:
        db.close()
