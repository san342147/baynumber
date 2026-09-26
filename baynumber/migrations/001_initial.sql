PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS bays (
  id INTEGER PRIMARY KEY,
  label TEXT NOT NULL UNIQUE COLLATE NOCASE,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assignments (
  id INTEGER PRIMARY KEY,
  bay_id INTEGER NOT NULL REFERENCES bays(id) ON DELETE RESTRICT,
  unit TEXT NOT NULL,
  plate TEXT NOT NULL,
  starts_at TEXT NOT NULL,
  ends_at TEXT,
  created_by TEXT NOT NULL,
  ended_by TEXT,
  CHECK (ends_at IS NULL OR ends_at >= starts_at)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_assignment_per_bay ON assignments(bay_id) WHERE ends_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS one_active_assignment_per_plate ON assignments(plate) WHERE ends_at IS NULL;

CREATE TABLE IF NOT EXISTS movements (
  id INTEGER PRIMARY KEY,
  bay_id INTEGER NOT NULL REFERENCES bays(id) ON DELETE RESTRICT,
  assignment_id INTEGER NOT NULL REFERENCES assignments(id) ON DELETE RESTRICT,
  kind TEXT NOT NULL CHECK(kind IN ('IN', 'OUT')),
  occurred_at TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  actor TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS movements_bay_order ON movements(bay_id, id DESC);
CREATE TRIGGER IF NOT EXISTS movements_no_update BEFORE UPDATE ON movements BEGIN SELECT RAISE(ABORT, 'movements are immutable'); END;
CREATE TRIGGER IF NOT EXISTS movements_no_delete BEFORE DELETE ON movements BEGIN SELECT RAISE(ABORT, 'movements are immutable'); END;

CREATE TABLE IF NOT EXISTS assignment_audit (
  id INTEGER PRIMARY KEY,
  assignment_id INTEGER NOT NULL REFERENCES assignments(id) ON DELETE RESTRICT,
  action TEXT NOT NULL CHECK(action IN ('CREATE', 'END')),
  occurred_at TEXT NOT NULL,
  actor TEXT NOT NULL,
  bay_label TEXT NOT NULL,
  unit TEXT NOT NULL,
  plate TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON assignment_audit BEGIN SELECT RAISE(ABORT, 'audit is immutable'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON assignment_audit BEGIN SELECT RAISE(ABORT, 'audit is immutable'); END;
