"""Input screening. FR-SEC-01, FR-SEC-04, FR-SEC-05."""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_MESSAGE_CHARS = 4000

_INJECTION_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "override-instructions",
        re.compile(
            r"ignore (all |any )?(previous|prior|above|earlier) "
            r"(instructions|prompts|rules)",
            re.IGNORECASE,
        ),
    ),
    (
        "override-instructions",
        re.compile(
            r"disregard (all |any )?(previous|prior|above|your) "
            r"(instructions|prompts|rules)",
            re.IGNORECASE,
        ),
    ),
    ("role-hijack", re.compile(r"\byou are now\b", re.IGNORECASE)),
    (
        "reveal-prompt",
        re.compile(
            r"(reveal|print|show|repeat).{0,40}(system prompt|hidden instructions|"
            r"developer message)",
            re.IGNORECASE,
        ),
    ),
    (
        "skip-confirmation",
        re.compile(
            r"(do not|don't|never) (ask|wait).{0,30}confirm",
            re.IGNORECASE,
        ),
    ),
    (
        "skip-confirmation",
        re.compile(
            r"bypass (the )?(confirmation|safety|security|approval)",
            re.IGNORECASE,
        ),
    ),
    (
        "fake-tool",
        re.compile(r"<\s*/?\s*(system|tool_call|tool_result)\s*>", re.IGNORECASE),
    ),
)

_SECRET_RULES: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(password\s*(is|:|=)\s*)(\S+)"),
    re.compile(r"(?i)(mfa(?:\s+code)?\s*(is|:|=)\s*)(\S+)"),
    re.compile(r"(?i)(passcode\s*(is|:|=)\s*)(\S+)"),
)


@dataclass(frozen=True)
class ScreenResult:
    blocked: bool
    rule: str | None
    message: str


def redact_secrets(text: str) -> tuple[str, bool]:
    """Replace pasted passwords and MFA codes before storage or model calls."""
    redacted = False

    def _hide(match: re.Match[str]) -> str:
        nonlocal redacted
        redacted = True
        return match.group(1) + "[redacted]"

    cleaned = text
    for pattern in _SECRET_RULES:
        cleaned = pattern.sub(_hide, cleaned)
    return cleaned, redacted


def screen_message(text: str) -> ScreenResult:
    """Block instruction override, confirmation bypass, and oversized messages."""
    if len(text) > MAX_MESSAGE_CHARS:
        return ScreenResult(
            True,
            "length",
            "That message is too long. Send the problem in under 4000 characters.",
        )
    for rule, pattern in _INJECTION_RULES:
        if pattern.search(text):
            return ScreenResult(
                True,
                rule,
                "I can't follow instructions that override the help desk rules or "
                "skip ticket confirmation. Tell me the IT problem in your own words.",
            )
    return ScreenResult(False, None, text)
