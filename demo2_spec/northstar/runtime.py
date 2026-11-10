"""Wire the local help desk. The UI and the tests both use this."""

from __future__ import annotations

from dataclasses import dataclass

from northstar.agent.fallback import FallbackAgent
from northstar.agent.loop import HelpDeskAgent
from northstar.config import Settings, load_settings
from northstar.db import Database
from northstar.llm.client import AzureClaudeClient
from northstar.rag.retriever import KnowledgeBase
from northstar.tools.registry import ServiceCatalog, ToolRegistry


@dataclass
class Runtime:
    settings: Settings
    database: Database
    knowledge: KnowledgeBase
    catalog: ServiceCatalog
    tools: ToolRegistry
    agent: HelpDeskAgent


def build_runtime(settings: Settings | None = None, llm=None, *, force_local: bool = False) -> Runtime:
    settings = settings or load_settings()
    database = Database(settings.db_path)
    database.initialize()
    knowledge = KnowledgeBase(settings.knowledge_dir)
    catalog = ServiceCatalog(settings.status_path)
    tools = ToolRegistry(knowledge, catalog)
    fallback = FallbackAgent(tools)
    if llm is None and settings.llm_configured and not force_local:
        llm = AzureClaudeClient(
            endpoint=settings.endpoint or "",
            api_key=settings.api_key or "",
            model=settings.model or "",
            api_version=settings.api_version,
            auth_style=settings.auth_style,
            timeout_s=settings.timeout_s,
        )
    agent = HelpDeskAgent(
        tools=tools,
        database=database,
        fallback=fallback,
        llm=llm,
        max_steps=settings.max_steps,
    )
    return Runtime(settings, database, knowledge, catalog, tools, agent)
