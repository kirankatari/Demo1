"""Exact confirmation phrases. FR-TOOL-03."""

from __future__ import annotations

import re

_CONFIRM = {
    "yes",
    "confirm",
    "confirmed",
    "create ticket",
    "create the ticket",
    "submit",
    "go ahead",
    "approve",
}
_CANCEL = {
    "no",
    "cancel",
    "stop",
    "never mind",
    "nevermind",
    "do not create it",
    "don't create it",
}
_PRIORITY_EDIT = re.compile(
    r"(?i)\b(?:change|set|make)\s+(?:the\s+)?priority\s+to\s+(low|medium|high|urgent)\b"
)


def _normalize(text: str) -> str:
    stripped = text.strip().lower()
    stripped = stripped.replace("’", "'")
    return re.sub(r"[.!?]+$", "", stripped).strip()


def is_exact_confirmation(text: str) -> bool:
    return _normalize(text) in _CONFIRM


def is_exact_cancellation(text: str) -> bool:
    return _normalize(text) in _CANCEL


def priority_edit(text: str) -> str | None:
    match = _PRIORITY_EDIT.search(text or "")
    if not match:
        return None
    return match.group(1).lower()
