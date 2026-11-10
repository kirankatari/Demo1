"""Environment configuration. FR-SEC-03, FR-DATA-02."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent


def load_env_files() -> None:
    for candidate in (Path.cwd() / ".env", PACKAGE_ROOT / ".env", REPO_ROOT / ".env"):
        if candidate.is_file():
            load_dotenv(candidate, override=False)


@dataclass(frozen=True)
class Settings:
    endpoint: str | None
    api_key: str | None
    model: str | None
    api_version: str
    auth_style: str
    db_path: Path
    knowledge_dir: Path
    status_path: Path
    timeout_s: float = 30.0
    max_steps: int = 4

    @property
    def llm_configured(self) -> bool:
        return bool(self.endpoint and self.api_key and self.model)

    def __repr__(self) -> str:
        return (
            "Settings("
            f"endpoint={self.endpoint!r}, api_key=[redacted], model={self.model!r}, "
            f"api_version={self.api_version!r}, auth_style={self.auth_style!r}, "
            f"db_path={self.db_path!r})"
        )


def load_settings() -> Settings:
    load_env_files()
    auth = os.getenv("AZURE_CLAUDE_AUTH_STYLE", "api-key").strip().lower() or "api-key"
    if auth not in {"api-key", "x-api-key", "bearer"}:
        auth = "api-key"
    return Settings(
        endpoint=_blank_to_none(os.getenv("AZURE_CLAUDE_ENDPOINT")),
        api_key=_blank_to_none(os.getenv("AZURE_CLAUDE_API_KEY")),
        model=_blank_to_none(os.getenv("AZURE_CLAUDE_MODEL")),
        api_version=os.getenv("AZURE_CLAUDE_API_VERSION", "2023-06-01").strip() or "2023-06-01",
        auth_style=auth,
        db_path=Path(os.getenv("NORTHSTAR_DB_PATH", PACKAGE_ROOT / "data" / "helpdesk.db")),
        knowledge_dir=Path(os.getenv("NORTHSTAR_KNOWLEDGE_DIR", PACKAGE_ROOT / "knowledge")),
        status_path=Path(os.getenv("NORTHSTAR_STATUS_PATH", PACKAGE_ROOT / "data" / "service_status.json")),
        timeout_s=float(os.getenv("AZURE_CLAUDE_TIMEOUT", "30")),
        max_steps=4,
    )


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
