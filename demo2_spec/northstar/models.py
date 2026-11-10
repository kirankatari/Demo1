"""Shared data types and enumerations. FR-TOOL-01, FR-TOOL-02, FR-SEC-03."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone


PRIORITIES = ("low", "medium", "high", "urgent")
CATEGORIES = (
    "network",
    "identity",
    "email",
    "endpoint",
    "meetings",
    "software",
    "printing",
    "other",
)
SERVICES = ("vpn", "email", "sso", "wifi", "m365", "zoom", "endpoint", "printing")
TICKET_STATUSES = ("open", "in_progress", "waiting_on_user", "resolved", "closed")
SERVICE_CATEGORY = {
    "vpn": "network",
    "wifi": "network",
    "email": "email",
    "sso": "identity",
    "m365": "software",
    "zoom": "meetings",
    "endpoint": "endpoint",
    "printing": "printing",
}

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*\S+"
)
_ANTHROPIC_TOKEN = re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def redact(text: str) -> str:
    """Remove credential-shaped fragments before they reach a trace or error."""
    cleaned = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[redacted]", text)
    return _ANTHROPIC_TOKEN.sub("[redacted]", cleaned)


def redact_obj(value):
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {str(key): redact_obj(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_obj(item) for item in value]
    return value


@dataclass
class Passage:
    passage_id: str
    document_id: str
    title: str
    heading: str
    text: str
    score: float = 0.0

    def citation(self) -> str:
        return f"[{self.passage_id}]"


@dataclass
class ServiceState:
    service_id: str
    name: str
    status: str
    since: str
    message: str


@dataclass
class TicketProposal:
    proposal_id: str
    action: str
    requester: str
    summary: str
    description: str
    category: str
    priority: str
    service: str | None = None
    ticket_id: str | None = None
    updates: dict = field(default_factory=dict)

    def public_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "action": self.action,
            "requester": self.requester,
            "summary": self.summary,
            "description": self.description,
            "category": self.category,
            "priority": self.priority,
            "service": self.service,
            "ticket_id": self.ticket_id,
            "updates": self.updates,
            "committed": False,
        }


@dataclass
class Ticket:
    id: str
    requester: str
    category: str
    priority: str
    service: str | None
    summary: str
    description: str
    status: str
    created_at: str
    updated_at: str


@dataclass
class Message:
    role: str
    content: str
    created_at: str = field(default_factory=utc_now)


@dataclass
class Conversation:
    id: str
    requester: str
    messages: list[Message] = field(default_factory=list)
    pending: TicketProposal | None = None
    last_retrieved_ids: list[str] = field(default_factory=list)
    last_passages: list[Passage] = field(default_factory=list)

    def add(self, role: str, content: str) -> Message:
        message = Message(role=role, content=content)
        self.messages.append(message)
        return message

    def llm_messages(self, limit: int = 20) -> list[dict]:
        """Plain chat turns only. Tool protocol stays inside a single turn. FR-CHAT-02."""
        window = [item for item in self.messages if item.role in {"user", "assistant"}][-limit:]
        return [{"role": item.role, "content": item.content} for item in window]


@dataclass
class Trace:
    turn_id: str
    mode: str
    stages: list[dict] = field(default_factory=list)
    total_ms: float = 0.0

    def stage(self, name: str, outcome: str, detail: str = "", **extra) -> None:
        item = {"stage": name, "outcome": outcome, "detail": redact(detail)}
        for key, value in extra.items():
            if key in {"thinking", "chain_of_thought"}:
                continue
            if key == "args":
                item["args"] = redact_obj(value)
            elif key == "latency_ms":
                item["latency_ms"] = round(float(value), 1)
            elif isinstance(value, str):
                item[key] = redact(value)
            else:
                item[key] = value
        self.stages.append(item)

    def to_dict(self) -> dict:
        return {
            "turn_id": self.turn_id,
            "mode": self.mode,
            "total_ms": round(self.total_ms, 1),
            "stages": self.stages,
        }


@dataclass
class ToolResult:
    outcome: str
    summary: str
    model_text: str
    safe_args: dict = field(default_factory=dict)
    pending: TicketProposal | None = None


@dataclass
class TurnResult:
    message: str
    trace: Trace
    pending: TicketProposal | None = None
    citations: list[str] = field(default_factory=list)
