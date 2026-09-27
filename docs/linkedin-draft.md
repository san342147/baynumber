# LinkedIn post — BayNumber 30-second demo

As a student, I learn best by building around a real workflow. My latest project is **BayNumber**, a parking-bay ledger for one apartment society. 🚗

During a busy shift, a guard needs to answer two questions quickly: “Which bay belongs to this vehicle?” and “Is it occupied now?” The 30-second demo shows the board, a vehicle lookup, an IN/OUT movement, and what happens when someone tries to record a second IN for an occupied bay.

I built it with Python 3.12, FastAPI, Pydantic, and SQLite. The ledger uses transactions and constraints to protect its event history; a secretary can manage assignments and export audit CSVs. Five local tests passed, including the concurrent IN conflict case.

The public preview and video use **synthetic data only**. The code is open source under the MIT License:
https://github.com/san342147/baynumber

I would appreciate feedback on the guard workflow and mobile UI.

#Python #FastAPI #SQLite #StudentDeveloper #BuildInPublic
