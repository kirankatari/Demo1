"""Citation checks. FR-RAG-03."""

from __future__ import annotations

import re
from dataclasses import dataclass

_CITE = re.compile(r"\[(DOC-[A-Z0-9-]+(?:#[a-z0-9-]+)?)\]")


@dataclass(frozen=True)
class GroundingResult:
    outcome: str
    detail: str
    citations: list[str]
    text: str


def check_grounding(text: str, retrieved_ids: list[str]) -> GroundingResult:
    retrieved = set(retrieved_ids)
    found = _CITE.findall(text or "")
    unsupported = [cite for cite in found if cite not in retrieved]
    cleaned = text or ""
    for cite in unsupported:
        cleaned = cleaned.replace(f"[{cite}]", "")
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    supported = [cite for cite in found if cite in retrieved]
    if unsupported:
        note = "Removed citations that were not in the retrieved passages."
        if note not in cleaned:
            cleaned = f"{cleaned}\n\n{note}".strip()
        return GroundingResult("unsupported_citation", note, supported, cleaned)
    if retrieved and not supported:
        return GroundingResult(
            "uncited",
            "Documents were retrieved but the answer did not cite them.",
            [],
            cleaned,
        )
    if not retrieved:
        return GroundingResult("not_applicable", "No documents were retrieved on this turn.", [], cleaned)
    return GroundingResult("supported", "Citations match retrieved passages.", supported, cleaned)
