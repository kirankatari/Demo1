"""SQLite ticket store. FR-DATA-01. Writes happen only after confirmation."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from northstar.models import Ticket, utc_now

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY,
    requester TEXT NOT NULL,
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    service TEXT,
    summary TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ticket_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT NOT NULL,
    event TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS eval_runs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""

_UPDATE_COLUMNS = {"priority", "status", "description", "summary", "category", "service"}


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def create_ticket(
        self,
        *,
        requester: str,
        category: str,
        priority: str,
        service: str | None,
        summary: str,
        description: str,
        detail: str,
    ) -> Ticket:
        now = utc_now()
        with self.connect() as connection:
            ticket_id = self._next_id(connection)
            connection.execute(
                """
                INSERT INTO tickets (
                    id, requester, category, priority, service, summary,
                    description, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
                """,
                (ticket_id, requester, category, priority, service, summary, description, now, now),
            )
            connection.execute(
                "INSERT INTO ticket_events (ticket_id, event, detail, created_at) VALUES (?, ?, ?, ?)",
                (ticket_id, "confirmed_create", detail, now),
            )
        return self.get_ticket(ticket_id)

    def update_ticket(self, ticket_id: str, fields: dict, *, detail: str) -> Ticket:
        current = self.get_ticket(ticket_id)
        if current is None:
            raise KeyError(ticket_id)
        assignments = []
        values: list[object] = []
        for column, value in fields.items():
            if column not in _UPDATE_COLUMNS:
                continue
            assignments.append(f"{column} = ?")
            values.append(value)
        if not assignments:
            raise ValueError("No allowed fields to update.")
        now = utc_now()
        assignments.append("updated_at = ?")
        values.append(now)
        values.append(ticket_id)
        with self.connect() as connection:
            connection.execute(
                f"UPDATE tickets SET {', '.join(assignments)} WHERE id = ?",
                values,
            )
            connection.execute(
                "INSERT INTO ticket_events (ticket_id, event, detail, created_at) VALUES (?, ?, ?, ?)",
                (ticket_id, "confirmed_update", detail, now),
            )
        ticket = self.get_ticket(ticket_id)
        if ticket is None:
            raise KeyError(ticket_id)
        return ticket

    def get_ticket(self, ticket_id: str) -> Ticket | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return _ticket_from_row(row) if row else None

    def list_tickets(self) -> list[Ticket]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM tickets ORDER BY created_at DESC, id DESC").fetchall()
        return [_ticket_from_row(row) for row in rows]

    def count_tickets(self) -> int:
        with self.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS c FROM tickets").fetchone()
        return int(row["c"])

    def save_eval(self, report: dict) -> str:
        run_id = report["id"]
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO eval_runs (id, created_at, payload) VALUES (?, ?, ?)",
                (run_id, report["started_at"], json.dumps(report)),
            )
        return run_id

    def latest_eval(self) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT payload FROM eval_runs ORDER BY created_at DESC, id DESC LIMIT 1"
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def _next_id(self, connection: sqlite3.Connection) -> str:
        row = connection.execute(
            "SELECT COALESCE(MAX(CAST(SUBSTR(id, 5) AS INTEGER)), 1000) AS n FROM tickets"
        ).fetchone()
        return f"TCK-{int(row['n']) + 1}"


def _ticket_from_row(row: sqlite3.Row) -> Ticket:
    return Ticket(
        id=row["id"],
        requester=row["requester"],
        category=row["category"],
        priority=row["priority"],
        service=row["service"],
        summary=row["summary"],
        description=row["description"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
