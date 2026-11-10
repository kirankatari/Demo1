"""Azure Claude Messages client and a scripted mock. FR-AGENT-03, FR-DATA-02, FR-EVAL-03."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import httpx

from northstar.models import redact

TOOL_SCHEMAS = [
    {
        "name": "search_knowledge",
        "description": "Search Northstar IT policy and troubleshooting documents before giving steps.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search words from the employee problem."},
                "top_k": {"type": "integer", "description": "Passages to return, from 1 to 5."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "check_service_status",
        "description": "Read simulated status for one Northstar IT service.",
        "input_schema": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "enum": ["vpn", "email", "sso", "wifi", "m365", "zoom", "endpoint", "printing"],
                }
            },
            "required": ["service"],
        },
    },
    {
        "name": "propose_ticket",
        "description": "Draft a new ticket. This does not create the ticket. The employee must confirm.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "description": {"type": "string"},
                "category": {
                    "type": "string",
                    "enum": ["network", "identity", "email", "endpoint", "meetings", "software", "printing", "other"],
                },
                "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                "service": {"type": "string"},
            },
            "required": ["summary", "description", "category", "priority"],
        },
    },
    {
        "name": "propose_ticket_update",
        "description": "Draft a change to an existing ticket id. This does not update the ticket.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                "status": {"type": "string"},
                "summary": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["ticket_id"],
        },
    },
]


class LLMError(Exception):
    """The model call did not return a usable message."""


class LLMTimeout(LLMError):
    """The model call exceeded the configured timeout."""


class LLMHTTPError(LLMError):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        super().__init__(f"Model request failed with HTTP {status_code}: {redact(detail)[:180]}")


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ModelResponse:
    stop_reason: str
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    latency_ms: float = 0.0
    public_content: list = field(default_factory=list)


class AzureClaudeClient:
    """Only this class opens an HTTP connection to the model endpoint."""

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        model: str,
        api_version: str = "2023-06-01",
        auth_style: str = "api-key",
        timeout_s: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.api_version = api_version
        self.auth_style = auth_style
        self.timeout_s = timeout_s
        self._transport = transport

    def complete(self, *, system: str, messages: list, tools: list, max_tokens: int = 1200) -> ModelResponse:
        headers = {
            "content-type": "application/json",
            "anthropic-version": self.api_version,
        }
        if self.auth_style == "bearer":
            headers["authorization"] = f"Bearer {self.api_key}"
        elif self.auth_style == "x-api-key":
            headers["x-api-key"] = self.api_key
        else:
            headers["api-key"] = self.api_key
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
            "tools": tools,
        }
        started = time.perf_counter()
        try:
            with httpx.Client(transport=self._transport, timeout=self.timeout_s) as client:
                response = client.post(self.endpoint, headers=headers, json=body)
        except httpx.TimeoutException as exc:
            raise LLMTimeout("The model request timed out.") from exc
        except httpx.HTTPError as exc:
            raise LLMError(type(exc).__name__) from exc
        latency_ms = (time.perf_counter() - started) * 1000
        if response.status_code >= 400:
            raise LLMHTTPError(response.status_code, response.text[:180])
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise LLMError("The model returned malformed JSON.") from exc
        return parse_anthropic_message(payload, latency_ms)


class MockLLMClient:
    """Replay scripted responses. Automated tests and the dashboard use this."""

    def __init__(self, script: list[dict] | None = None):
        self.script = list(script or [])
        self.calls: list[dict] = []

    def complete(self, *, system: str, messages: list, tools: list, max_tokens: int = 1200) -> ModelResponse:
        del max_tokens
        self.calls.append(
            {
                "system": system,
                "messages": messages,
                "tools": [tool["name"] for tool in tools],
            }
        )
        if not self.script:
            text = "I need a bit more detail about the device and the exact error."
            return ModelResponse(
                stop_reason="end_turn",
                text=text,
                latency_ms=1.0,
                public_content=[{"type": "text", "text": text}],
            )
        item = self.script.pop(0)
        return response_from_script(item)


def parse_anthropic_message(payload: dict, latency_ms: float) -> ModelResponse:
    """Drop provider thinking blocks before anything else can store them."""
    public = []
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    for block in payload.get("content") or []:
        block_type = block.get("type")
        if block_type == "thinking":
            continue
        if block_type == "text":
            public.append({"type": "text", "text": block.get("text", "")})
            text_parts.append(block.get("text", ""))
        elif block_type == "tool_use":
            arguments = block.get("input") if isinstance(block.get("input"), dict) else {}
            if isinstance(block.get("input"), str):
                try:
                    parsed = json.loads(block["input"])
                    arguments = parsed if isinstance(parsed, dict) else {}
                except json.JSONDecodeError:
                    arguments = {}
            public.append(
                {
                    "type": "tool_use",
                    "id": block.get("id", ""),
                    "name": block.get("name", ""),
                    "input": arguments,
                }
            )
            tool_calls.append(
                ToolCall(id=block.get("id", ""), name=block.get("name", ""), arguments=arguments)
            )
    return ModelResponse(
        stop_reason=payload.get("stop_reason") or ("tool_use" if tool_calls else "end_turn"),
        text="\n".join(part for part in text_parts if part).strip(),
        tool_calls=tool_calls,
        latency_ms=latency_ms,
        public_content=public,
    )


def response_from_script(item: dict) -> ModelResponse:
    tool_calls = []
    content = []
    for raw in item.get("tool_calls") or []:
        arguments = raw.get("arguments") or raw.get("input") or {}
        call = ToolCall(id=raw.get("id") or f"tool-{len(tool_calls)+1}", name=raw["name"], arguments=arguments)
        tool_calls.append(call)
        content.append({"type": "tool_use", "id": call.id, "name": call.name, "input": arguments})
    text = item.get("text") or ""
    if text:
        content.insert(0, {"type": "text", "text": text})
    return ModelResponse(
        stop_reason=item.get("stop_reason") or ("tool_use" if tool_calls else "end_turn"),
        text=text,
        tool_calls=tool_calls,
        latency_ms=float(item.get("latency_ms", 5)),
        public_content=content,
    )
