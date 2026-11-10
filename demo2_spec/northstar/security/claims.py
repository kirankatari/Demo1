"""Stop the assistant from claiming a ticket write that did not happen. FR-TOOL-03."""

from __future__ import annotations

import re

_CREATED = re.compile(
    r"(?i)\b(i have|i've|i’ve)\s+(created|opened|submitted|filed)\b"
    r"|\bticket\s+(has been|was)\s+(created|opened|submitted|filed)\b"
)


def guard_ticket_claims(text: str, *, committed: bool) -> str:
    if committed or not text:
        return text
    if not _CREATED.search(text):
        return text
    cleaned = _CREATED.sub("I prepared a draft", text)
    return cleaned.rstrip() + "\n\nThe ticket has not been created. Confirm it to submit."
