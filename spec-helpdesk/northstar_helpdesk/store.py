"""SQLite storage for transcripts, traces, and tickets. FR-DATA-01, FR-SEC-03.

Ticket rows are written only by confirm(). Staging a draft does not create one.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
PENDING_MINUTES = 30

PRIORITIES = {"P1", "P2", "P3", "P4"}
CATEGORIES = {"network", "access", "email", "hardware", "security", "other"}
STATUSES = {"open", "in_progress", "waiting", "resolved", "closed"}


class StorageError(RuntimeError):
    """The local database could not complete the request."""


class ConfirmationError(RuntimeError):
    """A confirm or cancel did not match an open draft."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_eastern(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(EASTERN).strftime("%b %d, %Y, %I:%M %p ET")


def _iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat()


class Store:
    def __init__(self, path: Path, clock=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock or utc_now
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init()

    def _init(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                requester TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                trace_id INTEGER,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                events_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                conversation_id TEXT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                requester TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pending_actions (
                token TEXT PRIMARY KEY,
                conversation_id TEXT,
                action TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                state TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def start_conversation(self, requester: str) -> str:
        conversation_id = "conv_" + secrets.token_hex(8)
        now = _iso(self.clock())
        with self._lock:
            self._conn.execute(
                "INSERT INTO conversations (id, requester, created_at) VALUES (?, ?, ?)",
                (conversation_id, requester.strip() or "Employee", now),
            )
            self._conn.commit()
        return conversation_id

    def set_requester(self, conversation_id: str, requester: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE conversations SET requester = ? WHERE id = ?",
                (requester.strip() or "Employee", conversation_id),
            )
            self._conn.commit()

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        trace_id: int | None = None,
    ) -> int:
        now = _iso(self.clock())
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO messages (conversation_id, role, content, trace_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_id, role, content, trace_id, now),
            )
            self._conn.commit()
            return int(cursor.lastrowid)

    def recent_messages(self, conversation_id: str, limit: int = 12) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT role, content FROM (
                    SELECT id, role, content FROM messages
                    WHERE conversation_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                ) ORDER BY id ASC
                """,
                (conversation_id, limit),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    def list_messages(self, conversation_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, role, content, trace_id, created_at
                FROM messages WHERE conversation_id = ? ORDER BY id ASC
                """,
                (conversation_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_trace(self, conversation_id: str, events: list[dict]) -> int:
        now = _iso(self.clock())
        with self._lock:
            cursor = self._conn.execute(
                """
                INSERT INTO traces (conversation_id, events_json, created_at)
                VALUES (?, ?, ?)
                """,
                (conversation_id, json.dumps(events), now),
            )
            self._conn.commit()
            return int(cursor.lastrowid)

    def get_trace(self, trace_id: int) -> list[dict]:
        with self._lock:
            row = self._conn.execute(
                "SELECT events_json FROM traces WHERE id = ?", (trace_id,)
            ).fetchone()
        if row is None:
            return []
        return json.loads(row["events_json"])

    def stage(self, conversation_id: str | None, action: str, payload: dict) -> dict:
        if action not in {"create", "update"}:
            raise StorageError("Unsupported pending action.")
        token = secrets.token_urlsafe(24)
        now = self.clock()
        record = {
            "token": token,
            "conversation_id": conversation_id,
            "action": action,
            "payload": payload,
            "created_at": _iso(now),
            "expires_at": _iso(now + timedelta(minutes=PENDING_MINUTES)),
            "state": "pending",
        }
        with self._lock:
            if conversation_id:
                self._conn.execute(
                    """
                    UPDATE pending_actions SET state = 'cancelled'
                    WHERE conversation_id = ? AND state = 'pending'
                    """,
                    (conversation_id,),
                )
            self._conn.execute(
                """
                INSERT INTO pending_actions
                (token, conversation_id, action, payload_json, created_at, expires_at, state)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """,
                (
                    token,
                    conversation_id,
                    action,
                    json.dumps(payload),
                    record["created_at"],
                    record["expires_at"],
                ),
            )
            self._conn.commit()
        return record

    def get_pending(self, conversation_id: str) -> dict | None:
        self._expire()
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM pending_actions
                WHERE conversation_id = ? AND state = 'pending'
                ORDER BY created_at DESC LIMIT 1
                """,
                (conversation_id,),
            ).fetchone()
        return _pending_row(row) if row else None

    def confirm(self, token: str) -> dict:
        self._expire()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM pending_actions WHERE token = ?", (token,)
            ).fetchone()
            if row is None or row["state"] != "pending":
                raise ConfirmationError(
                    "This confirmation is no longer valid. Stage the change again."
                )
            expires = datetime.fromisoformat(row["expires_at"])
            if self.clock() > expires:
                self._conn.execute(
                    "UPDATE pending_actions SET state = 'expired' WHERE token = ?",
                    (token,),
                )
                self._conn.commit()
                raise ConfirmationError(
                    "This confirmation expired. Stage the change again."
                )
            payload = json.loads(row["payload_json"])
            try:
                if row["action"] == "create":
                    ticket = self._insert_ticket_locked(row["conversation_id"], payload)
                elif row["action"] == "update":
                    ticket = self._apply_update_locked(payload)
                else:
                    raise ConfirmationError("Unsupported pending action.")
                self._conn.execute(
                    "UPDATE pending_actions SET state = 'confirmed' WHERE token = ?",
                    (token,),
                )
                self._conn.commit()
            except sqlite3.Error as exc:
                self._conn.rollback()
                raise StorageError("The local ticket database could not be updated.") from exc
        return {"action": row["action"], "ticket": ticket}

    def cancel(self, token: str) -> None:
        with self._lock:
            row = self._conn.execute(
                "SELECT state FROM pending_actions WHERE token = ?", (token,)
            ).fetchone()
            if row is None or row["state"] != "pending":
                raise ConfirmationError("There is no open draft to cancel.")
            self._conn.execute(
                "UPDATE pending_actions SET state = 'cancelled' WHERE token = ?",
                (token,),
            )
            self._conn.commit()

    def list_tickets(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM tickets ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_ticket(self, ticket_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM tickets WHERE id = ?", (ticket_id,)
            ).fetchone()
        return dict(row) if row else None

    def seed_ticket(self, **fields) -> dict:
        """Fixture helper for tests and offline evaluation. Not a model tool."""
        payload = {
            "title": fields["title"],
            "description": fields["description"],
            "category": fields["category"],
            "priority": fields["priority"],
            "requester": fields.get("requester", "Alex Chen"),
            "status": fields.get("status", "open"),
        }
        _validate_ticket_fields(payload, include_status=True)
        with self._lock:
            ticket = self._insert_ticket_locked(fields.get("conversation_id"), payload)
            self._conn.commit()
        return ticket

    def _expire(self) -> None:
        now = _iso(self.clock())
        with self._lock:
            self._conn.execute(
                """
                UPDATE pending_actions SET state = 'expired'
                WHERE state = 'pending' AND expires_at < ?
                """,
                (now,),
            )
            self._conn.commit()

    def _insert_ticket_locked(self, conversation_id: str | None, payload: dict) -> dict:
        count = self._conn.execute("SELECT COUNT(*) AS n FROM tickets").fetchone()["n"]
        ticket_id = f"NS-{1001 + count}"
        now = _iso(self.clock())
        status = payload.get("status", "open")
        record = {
            "id": ticket_id,
            "conversation_id": conversation_id,
            "title": payload["title"],
            "description": payload["description"],
            "category": payload["category"],
            "priority": payload["priority"],
            "status": status,
            "requester": payload["requester"],
            "created_at": now,
            "updated_at": now,
        }
        self._conn.execute(
            """
            INSERT INTO tickets
            (id, conversation_id, title, description, category, priority, status,
             requester, created_at, updated_at)
            VALUES (:id, :conversation_id, :title, :description, :category, :priority,
                    :status, :requester, :created_at, :updated_at)
            """,
            record,
        )
        return record

    def _apply_update_locked(self, payload: dict) -> dict:
        current = self._conn.execute(
            "SELECT * FROM tickets WHERE id = ?", (payload["ticket_id"],)
        ).fetchone()
        if current is None:
            raise ConfirmationError("That ticket does not exist.")
        status = payload.get("status", current["status"])
        priority = payload.get("priority", current["priority"])
        now = _iso(self.clock())
        self._conn.execute(
            """
            UPDATE tickets SET status = ?, priority = ?, updated_at = ? WHERE id = ?
            """,
            (status, priority, now, payload["ticket_id"]),
        )
        row = self._conn.execute(
            "SELECT * FROM tickets WHERE id = ?", (payload["ticket_id"],)
        ).fetchone()
        return dict(row)

    def ticket_count(self) -> int:
        with self._lock:
            return int(
                self._conn.execute("SELECT COUNT(*) AS n FROM tickets").fetchone()["n"]
            )


def _pending_row(row: sqlite3.Row) -> dict:
    return {
        "token": row["token"],
        "conversation_id": row["conversation_id"],
        "action": row["action"],
        "payload": json.loads(row["payload_json"]),
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
        "state": row["state"],
    }


def validate_create_draft(arguments: dict, requester: str) -> dict:
    draft = {
        "title": _require_text(arguments, "title", 8, 120),
        "description": _require_text(arguments, "description", 20, 2000),
        "category": _require_choice(arguments, "category", CATEGORIES),
        "priority": _require_choice(arguments, "priority", PRIORITIES),
        "requester": _require_text(
            {"requester": arguments.get("requester") or requester},
            "requester",
            2,
            80,
        ),
    }
    return draft


def validate_update_draft(arguments: dict, ticket_exists) -> dict:
    ticket_id = _require_text(arguments, "ticket_id", 4, 20)
    if not ticket_id.startswith("NS-") or not ticket_id[3:].isdigit():
        raise ValueError("ticket_id must look like NS-1001.")
    status = arguments.get("status")
    priority = arguments.get("priority")
    if status in ("", None) and priority in ("", None):
        raise ValueError("Provide a status or a priority to change.")
    draft: dict = {"ticket_id": ticket_id}
    if status not in ("", None):
        if status not in STATUSES:
            raise ValueError("status must be one of: " + ", ".join(sorted(STATUSES)))
        draft["status"] = status
    if priority not in ("", None):
        if priority not in PRIORITIES:
            raise ValueError("priority must be one of: " + ", ".join(sorted(PRIORITIES)))
        draft["priority"] = priority
    if not ticket_exists(ticket_id):
        raise ValueError(f"{ticket_id} does not exist.")
    return draft


def _validate_ticket_fields(payload: dict, include_status: bool = False) -> None:
    _require_text(payload, "title", 8, 120)
    _require_text(payload, "description", 20, 2000)
    _require_choice(payload, "category", CATEGORIES)
    _require_choice(payload, "priority", PRIORITIES)
    _require_text(payload, "requester", 2, 80)
    if include_status:
        _require_choice(payload, "status", STATUSES)


def _require_text(arguments: dict, name: str, minimum: int, maximum: int) -> str:
    value = arguments.get(name)
    if not isinstance(value, str):
        raise ValueError(f"{name} is required.")
    cleaned = " ".join(value.split())
    if len(cleaned) < minimum or len(cleaned) > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum} characters.")
    return cleaned


def _require_choice(arguments: dict, name: str, choices: set[str]) -> str:
    value = arguments.get(name)
    if value not in choices:
        raise ValueError(f"{name} must be one of: " + ", ".join(sorted(choices)))
    return value
