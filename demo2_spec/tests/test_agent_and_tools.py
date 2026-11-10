"""Tools, confirmation, and the agent loop."""

from __future__ import annotations

import json

from northstar.agent.loop import trace_has_private_fields
from northstar.llm.client import LLMTimeout, MockLLMClient
from northstar.models import Conversation
from northstar.runtime import build_runtime
from northstar.samples import SAMPLE_VPN_QUESTION


def test_vpn_status_degraded(runtime):
    result = runtime.tools.execute("check_service_status", {"service": "vpn"}, Conversation(id="c", requester="A"))
    payload = json.loads(result.model_text)
    assert result.outcome == "success"
    assert payload["status"] == "degraded"
    assert "US-Central" in payload["message"]


def test_unknown_service_is_error(runtime):
    result = runtime.tools.execute("check_service_status", {"service": "payroll"}, Conversation(id="c", requester="A"))
    assert result.outcome == "error"
    assert "vpn" in result.model_text


def test_unknown_tool_rejected(runtime, conversation):
    result = runtime.tools.execute("create_ticket", {"summary": "nope"}, conversation)
    assert result.outcome == "rejected"
    assert runtime.database.count_tickets() == 0


def test_propose_does_not_insert_ticket(runtime, conversation):
    result = runtime.tools.execute("propose_ticket", _vpn_ticket(), conversation)
    assert result.outcome == "success"
    assert conversation.pending is not None
    assert runtime.database.count_tickets() == 0
    assert '"committed": false' in result.model_text


def test_invalid_proposal_rejected(runtime, conversation):
    args = _vpn_ticket()
    args["summary"] = "bad"
    args["priority"] = "panic"
    result = runtime.tools.execute("propose_ticket", args, conversation)
    assert result.outcome == "error"
    assert conversation.pending is None
    assert runtime.database.count_tickets() == 0


def test_hero_fallback_end_to_end(runtime):
    conversation = Conversation(id="hero", requester="Alex Morgan")
    result = runtime.agent.handle_message(conversation, SAMPLE_VPN_QUESTION)
    tools = [stage.get("tool") for stage in result.trace.stages if stage.get("stage") == "tool_call"]
    assert "search_knowledge" in tools
    assert "check_service_status" in tools
    assert "propose_ticket" in tools
    assert "degraded" in result.message.lower()
    assert "Sign out of GlobalProtect" in result.message
    assert "US-Central" in result.message
    assert "?" in result.message
    assert "What I did:" in result.message
    assert result.pending is not None and result.pending.priority == "urgent"
    assert runtime.database.count_tickets() == 0
    assert not trace_has_private_fields(result.trace.to_dict())


def test_fallback_citations_are_grounded(runtime):
    conversation = Conversation(id="cite", requester="Alex Morgan")
    result = runtime.agent.handle_message(conversation, SAMPLE_VPN_QUESTION)
    grounding = next(stage for stage in result.trace.stages if stage["stage"] == "grounding")
    assert grounding["outcome"] == "supported"
    assert "[DOC-VPN-002#" in result.message


def test_greeting_skips_tools(runtime):
    conversation = Conversation(id="hi", requester="Alex Morgan")
    result = runtime.agent.handle_message(conversation, "hello")
    assert not any(stage.get("stage") == "tool_call" for stage in result.trace.stages)
    assert runtime.database.count_tickets() == 0


def test_exact_yes_commits_ticket(runtime):
    conversation = Conversation(id="yes", requester="Alex Morgan")
    runtime.agent.handle_message(conversation, SAMPLE_VPN_QUESTION)
    result = runtime.agent.handle_message(conversation, "yes")
    assert runtime.database.count_tickets() == 1
    stored = runtime.database.list_tickets()[0]
    assert stored.id.startswith("TCK-")
    assert stored.priority == "urgent"
    assert result.pending is None
    reopened = build_runtime(runtime.settings, llm=None, force_local=True)
    assert reopened.database.count_tickets() == 1


def test_yes_with_extra_text_does_not_commit(runtime):
    conversation = Conversation(id="extra", requester="Alex Morgan")
    runtime.agent.handle_message(conversation, SAMPLE_VPN_QUESTION)
    runtime.agent.handle_message(conversation, "yes please create it now")
    assert runtime.database.count_tickets() == 0


def test_cancel_does_not_insert(runtime):
    conversation = Conversation(id="cancel", requester="Alex Morgan")
    runtime.agent.handle_message(conversation, SAMPLE_VPN_QUESTION)
    result = runtime.agent.handle_message(conversation, "cancel")
    assert runtime.database.count_tickets() == 0
    assert result.pending is None


def test_priority_edit_updates_draft_only(runtime):
    conversation = Conversation(id="edit", requester="Alex Morgan")
    runtime.agent.handle_message(conversation, SAMPLE_VPN_QUESTION)
    result = runtime.agent.handle_message(conversation, "change priority to low")
    assert runtime.database.count_tickets() == 0
    assert result.pending is not None
    assert result.pending.priority == "low"


def test_update_requires_confirmation(runtime):
    conversation = Conversation(id="upd", requester="Alex Morgan")
    runtime.agent.handle_message(conversation, SAMPLE_VPN_QUESTION)
    runtime.agent.handle_message(conversation, "yes")
    ticket_id = runtime.database.list_tickets()[0].id
    staged = runtime.tools.execute(
        "propose_ticket_update",
        {"ticket_id": ticket_id, "priority": "low"},
        conversation,
    )
    assert staged.outcome == "success"
    assert runtime.database.get_ticket(ticket_id).priority == "urgent"
    runtime.agent.commit_pending(conversation)
    assert runtime.database.get_ticket(ticket_id).priority == "low"


def test_mock_agent_searches_then_answers(settings):
    script = [
        {
            "stop_reason": "tool_use",
            "tool_calls": [
                {
                    "id": "c1",
                    "name": "search_knowledge",
                    "arguments": {"query": "GlobalProtect disconnects US-Central gateway"},
                }
            ],
        },
        {
            "stop_reason": "end_turn",
            "text": "Switch the gateway to US-Central. [DOC-VPN-002#switch-gateway]",
        },
    ]
    mock = MockLLMClient(script)
    runtime = build_runtime(settings, llm=mock)
    conversation = Conversation(id="mock", requester="Alex Morgan")
    result = runtime.agent.handle_message(conversation, "GlobalProtect keeps dropping.")
    assert any(stage.get("tool") == "search_knowledge" for stage in result.trace.stages)
    grounding = next(stage for stage in result.trace.stages if stage["stage"] == "grounding")
    assert grounding["outcome"] == "supported"
    assert not trace_has_private_fields(result.trace.to_dict())


def test_trace_has_no_private_reasoning(runtime):
    conversation = Conversation(id="trace", requester="Alex Morgan")
    result = runtime.agent.handle_message(conversation, SAMPLE_VPN_QUESTION)
    payload = result.trace.to_dict()
    assert "thinking" not in json.dumps(payload)
    assert not trace_has_private_fields(payload)


def test_memory_includes_prior_turn(settings):
    mock = MockLLMClient(
        [
            {"stop_reason": "end_turn", "text": "Which gateway is selected?"},
            {"stop_reason": "end_turn", "text": "Thanks, that helps."},
        ]
    )
    runtime = build_runtime(settings, llm=mock)
    conversation = Conversation(id="mem", requester="Alex Morgan")
    runtime.agent.handle_message(conversation, "The VPN client is open on my Windows laptop.")
    runtime.agent.handle_message(conversation, "It drops every five minutes.")
    blob = json.dumps(mock.calls[1]["messages"])
    assert "The VPN client is open on my Windows laptop." in blob


def test_loop_stops_at_max_steps(settings):
    script = [
        {"stop_reason": "tool_use", "tool_calls": [{"name": "check_service_status", "arguments": {"service": "vpn"}}]}
        for _ in range(6)
    ]
    mock = MockLLMClient(script)
    runtime = build_runtime(settings, llm=mock)
    conversation = Conversation(id="bound", requester="Alex Morgan")
    result = runtime.agent.handle_message(conversation, "Keep checking VPN.")
    assert len(mock.calls) == 4
    assert any(stage.get("outcome") == "max_steps" for stage in result.trace.stages)


def test_unsupported_citation_is_stripped(settings):
    mock = MockLLMClient(
        [
            {
                "stop_reason": "tool_use",
                "tool_calls": [
                    {"name": "search_knowledge", "arguments": {"query": "VPN disconnect GlobalProtect gateway"}}
                ],
            },
            {"stop_reason": "end_turn", "text": "Do this undocumented step. [DOC-NOPE-999#missing]"},
        ]
    )
    runtime = build_runtime(settings, llm=mock)
    conversation = Conversation(id="badcite", requester="Alex Morgan")
    result = runtime.agent.handle_message(conversation, "VPN help")
    grounding = next(stage for stage in result.trace.stages if stage["stage"] == "grounding")
    assert grounding["outcome"] == "unsupported_citation"
    assert "DOC-NOPE-999#missing" not in result.message


def test_api_timeout_uses_local_documents(settings):
    class TimeoutClient:
        def complete(self, **kwargs):
            del kwargs
            raise LLMTimeout("timed out")

    runtime = build_runtime(settings, llm=TimeoutClient())
    conversation = Conversation(id="timeout", requester="Alex Morgan")
    result = runtime.agent.handle_message(conversation, SAMPLE_VPN_QUESTION)
    assert "timed out" in result.message.lower()
    assert "degraded" in result.message.lower()
    assert runtime.database.count_tickets() == 0


def _vpn_ticket() -> dict:
    return {
        "summary": "VPN disconnect before a client presentation",
        "description": "Repeated GlobalProtect disconnects on the remote gateway.",
        "category": "network",
        "priority": "urgent",
        "service": "vpn",
    }
