# BayNumber demo script (about 90 seconds)

**0:00–0:12 — Public preview.** Open `http://127.0.0.1:8000`. Show the underground night board and its four status colors. State that this preview is synthetic; it has no real plates or units.

**0:12–0:25 — Sign in.** Use the guard account from your local `.env`. Search for a seeded demo plate (for a demo database, `DEMO1234`). Point out the bay, unit, and current occupancy. Never show a real resident record in a public recording.

**0:25–0:42 — Movement.** Click **Record OUT** on occupied A-04, refresh, then **Record IN**. Show the state switch and that a second IN produces a red conflict with a useful message.

**0:42–1:02 — Secretary.** Sign out and use the admin account. Create a new bay, assign a synthetic plate and unit, and show the assignment on the board. Try to end an occupied assignment; explain that an OUT must be recorded first.

**1:02–1:20 — Audit.** Export the movement CSV and assignment audit CSV. Show the stable headers, actor, and UTC timestamps. Mention that event and audit rows are immutable in SQLite.

**1:20–1:30 — Close.** Show the README test results and privacy note: local SQLite storage, no contacts collected, no real data shipped.
