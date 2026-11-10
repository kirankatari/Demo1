"""Simulated service status. FR-DATA-02, FR-TOOL-01."""

from __future__ import annotations

import json
import re
from pathlib import Path

ALIASES = {
    "vpn": "vpn",
    "northstar connect": "vpn",
    "northstar connect vpn": "vpn",
    "remote access": "vpn",
    "email": "email",
    "outlook": "email",
    "mail": "email",
    "teams": "teams",
    "sso": "sso",
    "single sign-on": "sso",
    "single sign on": "sso",
    "wifi": "wifi",
    "wi-fi": "wifi",
    "wi fi": "wifi",
    "office wifi": "wifi",
    "office wi-fi": "wifi",
    "catalog": "catalog",
    "software catalog": "catalog",
}


def resolve_service(value: str) -> str | None:
    raw = " ".join(value.lower().replace("_", " ").split())
    candidates = [raw, " ".join(raw.replace("-", " ").split())]
    for candidate in candidates:
        if candidate in ALIASES:
            return ALIASES[candidate]
    return None


def mentioned_services(text: str) -> list[str]:
    """Find service aliases in employee text for the no-model fallback only."""
    lower = text.lower()
    matches: list[tuple[int, str]] = []
    occupied: list[tuple[int, int]] = []
    for alias, service_id in sorted(
        ALIASES.items(), key=lambda item: len(item[0]), reverse=True
    ):
        pattern = r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
        for match in re.finditer(pattern, lower):
            span = match.span()
            if any(span[0] < end and span[1] > start for start, end in occupied):
                continue
            occupied.append(span)
            matches.append((span[0], service_id))
    found: list[str] = []
    for _, service_id in sorted(matches):
        if service_id not in found:
            found.append(service_id)
    return found


class ServiceCatalog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._services: dict[str, dict] = json.loads(self.path.read_text(encoding="utf-8"))

    def ids(self) -> list[str]:
        return sorted(self._services)

    def check(self, service_id: str) -> dict:
        if not isinstance(service_id, str) or not service_id.strip():
            return {"ok": False, "error": "service_id is required."}
        resolved = resolve_service(service_id)
        if resolved is None or resolved not in self._services:
            return {
                "ok": False,
                "error": "Unknown service. Use one of: " + ", ".join(self.ids()),
            }
        row = self._services[resolved]
        return {"ok": True, "service_id": resolved, **row}

    def list_public(self) -> list[dict]:
        return [{"service_id": key, **value} for key, value in self._services.items()]
