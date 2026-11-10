"""Shared fixtures for the spec-driven help desk."""

from __future__ import annotations

from pathlib import Path

import pytest

from northstar.config import PACKAGE_ROOT, Settings
from northstar.models import Conversation
from northstar.runtime import build_runtime


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        endpoint=None,
        api_key=None,
        model=None,
        api_version="2023-06-01",
        auth_style="api-key",
        db_path=tmp_path / "helpdesk.db",
        knowledge_dir=PACKAGE_ROOT / "knowledge",
        status_path=PACKAGE_ROOT / "data" / "service_status.json",
        timeout_s=5,
        max_steps=4,
    )


@pytest.fixture
def runtime(settings: Settings):
    return build_runtime(settings, llm=None, force_local=True)


@pytest.fixture
def conversation() -> Conversation:
    return Conversation(id="conv-test", requester="Alex Morgan")
