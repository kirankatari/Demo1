"""Claude on Azure. This module does not import tickets, retrieval, or tools."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from helpdesk.config import AzureConfig

_SECRET_TEXT = re.compile(
    r"(?i)(sk-ant-[A-Za-z0-9_\-]{6,}|api[_-]?key['\"]?\s*[:=]\s*\S+|[A-Za-z0-9_\-]{32,})"
)


class ModelError(RuntimeError):
    """A model call failed. The message is safe to show and to store."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ModelResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"
    latency_ms: float = 0.0

    def assistant_blocks(self) -> list[dict]:
        blocks: list[dict] = []
        if self.text:
            blocks.append({"type": "text", "text": self.text})
        for call in self.tool_calls:
            blocks.append(
                {
                    "type": "tool_use",
                    "id": call.id,
                    "name": call.name,
                    "input": call.arguments,
                }
            )
        return blocks or [{"type": "text", "text": ""}]


class ScriptedModel:
    """Offline stand-in. Tests and the evaluation dashboard use this, not Azure."""

    def __init__(self, steps: list[dict] | None = None):
        self.steps = list(steps or [])
        self.calls: list[dict] = []
        self.model_name = "scripted"

    def complete(self, *, system: str, messages: list[dict], tools: list[dict] | None):
        self.calls.append({"system": system, "messages": messages, "tools": tools})
        if not self.steps:
            return ModelResponse(text="I need to stop here.", latency_ms=1.0)
        item = self.steps.pop(0)
        calls = [ToolCall(**call) for call in item.get("tool_calls", [])]
        return ModelResponse(
            text=item.get("text", ""),
            tool_calls=calls,
            stop_reason=item.get("stop_reason", "tool_use" if calls else "end_turn"),
            latency_ms=float(item.get("latency_ms", 4.0)),
        )


class AnthropicAzureModel:
    """Isolated Azure Claude client. Business rules do not live here."""

    def __init__(self, config: AzureConfig, timeout: float = 45.0):
        from anthropic import AnthropicFoundry

        self.model_name = config.model
        self._client = AnthropicFoundry(
            api_key=config.api_key,
            base_url=config.endpoint,
            timeout=timeout,
            max_retries=1,
        )

    def complete(self, *, system: str, messages: list[dict], tools: list[dict] | None):
        kwargs: dict = {
            "model": self.model_name,
            "max_tokens": 900,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        started = time.perf_counter()
        try:
            response = self._client.messages.create(**kwargs)
        except Exception as exc:
            raise ModelError(_public_model_error(exc)) from exc
        latency_ms = (time.perf_counter() - started) * 1000
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text_parts.append(block.text)
            elif block_type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=dict(block.input),
                    )
                )
        return ModelResponse(
            text="\n".join(part.strip() for part in text_parts if part.strip()).strip(),
            tool_calls=tool_calls,
            stop_reason=getattr(response, "stop_reason", None) or "end_turn",
            latency_ms=latency_ms,
        )


def _public_model_error(exc: Exception) -> str:
    text = _SECRET_TEXT.sub("[redacted]", str(exc))
    text = " ".join(text.split())
    if len(text) > 280:
        text = text[:280].rstrip() + "..."
    return f"The model request failed ({exc.__class__.__name__}): {text}"
