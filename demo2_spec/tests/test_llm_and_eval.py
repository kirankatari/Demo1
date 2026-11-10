"""Model client parsing and the shared evaluation harness."""

from __future__ import annotations

import json

import httpx

from northstar.eval.harness import run_evaluation
from northstar.llm.client import AzureClaudeClient


def test_azure_client_strips_thinking():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["api-key"] == "test-key"
        body = json.loads(request.content.decode())
        assert body["model"] == "claude-test"
        assert body["system"]
        return httpx.Response(
            200,
            json={
                "stop_reason": "tool_use",
                "content": [
                    {"type": "thinking", "thinking": "secret chain of thought"},
                    {"type": "text", "text": "Checking documents."},
                    {"type": "tool_use", "id": "t1", "name": "search_knowledge", "input": {"query": "vpn"}},
                ],
            },
        )

    client = AzureClaudeClient(
        endpoint="https://example.test/anthropic/v1/messages",
        api_key="test-key",
        model="claude-test",
        transport=httpx.MockTransport(handler),
    )
    response = client.complete(system="You are a help desk.", messages=[{"role": "user", "content": "vpn"}], tools=[])
    blob = json.dumps(response.public_content)
    assert "secret chain of thought" not in blob
    assert response.tool_calls[0].name == "search_knowledge"
    assert response.text == "Checking documents."


def test_azure_error_redacts_key_material():
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(401, text="rejected sk-ant-abcdefghijklmnopqrstuvwxyz")

    client = AzureClaudeClient(
        endpoint="https://example.test/anthropic/v1/messages",
        api_key="test-key",
        model="claude-test",
        transport=httpx.MockTransport(handler),
    )
    try:
        client.complete(system="s", messages=[], tools=[])
    except Exception as exc:  # noqa: BLE001 - asserting the public error text
        message = str(exc)
    else:
        raise AssertionError("expected an HTTP error")
    assert "HTTP 401" in message
    assert "sk-ant-abcdefghijklmnopqrstuvwxyz" not in message


def test_eval_harness_passes():
    report = run_evaluation()
    failed = [item for item in report["results"] if not item["passed"]]
    assert not failed, failed
    assert report["tool_success_rate"] is not None
    assert report["mean_latency_ms"] >= 0
    assert report["retrieval_hit_rate"] == 1
