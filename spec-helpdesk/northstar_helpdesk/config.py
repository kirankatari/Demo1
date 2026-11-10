"""Azure Anthropic settings. FR-OPS-01, FR-OPS-02, FR-SEC-04."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


class ConfigurationError(RuntimeError):
    """The Azure endpoint, API key, or model name is missing."""


@dataclass(frozen=True)
class AzureConfig:
    endpoint: str
    api_key: str
    model: str

    def __repr__(self) -> str:
        return (
            f"AzureConfig(endpoint={self.endpoint!r}, model={self.model!r}, "
            "api_key='[redacted]')"
        )


def load_azure_config(env_file: Path | None = None) -> AzureConfig:
    """Load the three Azure settings. Existing process variables win over .env."""
    load_dotenv(env_file or ROOT / ".env", override=False)
    values = {
        "AZURE_ANTHROPIC_ENDPOINT": os.getenv("AZURE_ANTHROPIC_ENDPOINT", "").strip(),
        "AZURE_ANTHROPIC_API_KEY": os.getenv("AZURE_ANTHROPIC_API_KEY", "").strip(),
        "AZURE_ANTHROPIC_MODEL": os.getenv("AZURE_ANTHROPIC_MODEL", "").strip(),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ConfigurationError(
            "Missing " + ", ".join(missing) + ". Add them to .env. See .env.example."
        )
    return AzureConfig(
        endpoint=values["AZURE_ANTHROPIC_ENDPOINT"],
        api_key=values["AZURE_ANTHROPIC_API_KEY"],
        model=values["AZURE_ANTHROPIC_MODEL"],
    )
