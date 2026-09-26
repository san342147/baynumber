# LinkedIn draft — verify before posting

I built **BayNumber**, a small parking-bay ledger for an apartment society.

The guard view answers two shift questions quickly: “Which bay belongs to this plate?” and “Is it occupied now?” A secretary can create bays, change assignments, and export movement and assignment audit CSVs. The public board is synthetic and hides plate and unit details.

Under the hood: Python 3.12, FastAPI, Pydantic, and SQLite. SQLite write transactions serialize competing movement requests. In the local test run, two simultaneous IN attempts produced exactly one success, one conflict, and one event. The five automated tests passed, covering the clean workflow, validation, constraints, transactions, permissions, CSV headers, and missing-database errors.

I kept the scope deliberate: one society, local storage, no contact fields, and no AI dependency. There are still production gaps to address before a wider rollout, including account provisioning, HTTPS deployment, backups, and multi-device operational testing.

Repo: https://github.com/san342147/baynumber

#Python #FastAPI #SQLite #ProductEngineering
