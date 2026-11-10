"""Wire the local help desk. FR-AGENT-04 when Azure settings are missing."""

from __future__ import annotations

from pathlib import Path

from northstar_helpdesk.agent import Agent
from northstar_helpdesk.config import ConfigurationError, load_azure_config
from northstar_helpdesk.model_client import AnthropicAzureModel
from northstar_helpdesk.rag import KnowledgeBase
from northstar_helpdesk.services import ServiceCatalog
from northstar_helpdesk.store import Store


class HelpDesk:
    def __init__(self, agent: Agent, store: Store, model_name: str | None):
        self.agent = agent
        self.store = store
        self.model_name = model_name

    @property
    def model_configured(self) -> bool:
        return self.model_name is not None

    @classmethod
    def open(
        cls,
        root: Path,
        db_path: Path | None = None,
        model=None,
        load_model: bool = True,
    ) -> "HelpDesk":
        root = Path(root)
        store = Store(db_path or root / "data" / "helpdesk.db")
        knowledge = KnowledgeBase(root / "knowledge")
        catalog = ServiceCatalog(root / "data" / "services.json")
        model_name = None
        if model is not None:
            model_name = getattr(model, "model_name", "scripted")
        elif load_model:
            try:
                config = load_azure_config(root / ".env")
            except ConfigurationError:
                model = None
            else:
                model = AnthropicAzureModel(config)
                model_name = config.model
        agent = Agent(model=model, knowledge=knowledge, catalog=catalog, store=store)
        return cls(agent, store, model_name)
