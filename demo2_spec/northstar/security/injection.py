"""Lexical prompt-injection screen. FR-SEC-01.

The matcher is intentionally narrow. It is a gate in front of the model, not a
claim that every paraphrase can be detected. Ticket writes still require a
separate confirmation step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PATTERNS = (
    re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|rules|prompts)"),
    re.compile(r"(?i)disregard\s+(the\s+)?(system|developer|previous|prior)\s+(prompt|instructions|rules)"),
    re.compile(r"(?i)\byou\s+are\s+now\b"),
    re.compile(r"(?i)\bact\s+as\s+(a\s+)?(system|developer|dan|unrestricted)\b"),
    re.compile(
        r"(?i)\b(reveal|show|print|dump|exfiltrate)\b.{0,40}\b(api[_ -]?key|secret|system prompt|credentials|\.env)\b"
    ),
    re.compile(r"(?i)\b(create|open|file|update|modify|change)\b.{0,40}\bticket\b.{0,40}\bwithout\b.{0,20}\bconfirm"),
    re.compile(r"(?i)\bbypass\b.{0,20}\bconfirm"),
    re.compile(r"(?i)do\s+not\s+(ask|require|wait)\s+for\s+confirm"),
    re.compile(r"(?i)</?\s*(system|instructions)\s*>"),
    re.compile(r"(?i)<\|\s*im_start\s*\|>"),
    re.compile(r"(?i)\bnew\s+instructions\s*:"),
    re.compile(r"(?i)\bforget\s+(all\s+)?(your\s+)?(rules|instructions)\b"),
)


@dataclass(frozen=True)
class ScreenResult:
    blocked: bool
    reason: str


def screen_text(text: str) -> ScreenResult:
    for pattern in _PATTERNS:
        if pattern.search(text or ""):
            return ScreenResult(True, "The message asks to override help desk rules.")
    return ScreenResult(False, "No override pattern matched.")


def sanitize_passage(text: str) -> str:
    """Replace untrusted instruction text inside a retrieved passage."""
    if screen_text(text).blocked:
        return "This passage was removed because it contained an untrusted instruction."
    return text
