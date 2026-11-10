"""Bounded help desk agent. FR-AGENT-01 through FR-AGENT-03, FR-CHAT-04, FR-OPS-01."""

from __future__ import annotations

import time
import uuid

from northstar.agent.fallback import FallbackAgent
from northstar.agent.grounding import check_grounding
from northstar.agent.prompts import SYSTEM_PROMPT
from northstar.db import Database
from northstar.llm.client import TOOL_SCHEMAS, LLMError, LLMHTTPError, LLMTimeout
from northstar.models import Conversation, TicketProposal, Trace, TurnResult
from northstar.security.claims import guard_ticket_claims
from northstar.security.confirmation import is_exact_cancellation, is_exact_confirmation, priority_edit
from northstar.security.injection import screen_text
from northstar.tools.registry import ToolRegistry

_PRIVATE_KEYS = {"thinking", "chain_of_thought"}


class HelpDeskAgent:
    def __init__(
        self,
        *,
        tools: ToolRegistry,
        database: Database,
        fallback: FallbackAgent,
        llm=None,
        max_steps: int = 4,
    ):
        self.tools = tools
        self.database = database
        self.fallback = fallback
        self.llm = llm
        self.max_steps = max_steps

    def handle_message(self, conversation: Conversation, user_text: str) -> TurnResult:
        started = time.perf_counter()
        mode = "llm" if self.llm is not None else "fallback"
        trace = Trace(turn_id=f"turn-{uuid.uuid4().hex[:8]}", mode=mode)
        screen = screen_text(user_text)
        trace.stage("input_screen", "blocked" if screen.blocked else "allowed", screen.reason)
        if screen.blocked:
            reply = (
                "I can't follow instructions that override help desk rules or ask for secrets. "
                "Restate the IT problem, such as which system failed and what you already tried."
            )
            conversation.add("user", user_text)
            conversation.add("assistant", reply)
            trace.total_ms = _elapsed(started)
            return TurnResult(reply, trace, conversation.pending)

        if conversation.pending and is_exact_confirmation(user_text):
            return self.commit_pending(conversation, trace=trace, started=started, user_text=user_text)
        if conversation.pending and is_exact_cancellation(user_text):
            return self.cancel_pending(conversation, trace=trace, started=started, user_text=user_text)
        edited = priority_edit(user_text) if conversation.pending else None
        if conversation.pending and edited:
            conversation.pending.priority = edited
            conversation.add("user", user_text)
            reply = (
                f"I updated the draft priority to {edited}. The ticket is still not submitted. "
                "Choose Confirm to submit this draft or Cancel to drop it."
            )
            conversation.add("assistant", reply)
            trace.stage("confirmation_gate", "draft_updated", f"priority={edited}")
            trace.total_ms = _elapsed(started)
            return TurnResult(reply, trace, conversation.pending)

        conversation.add("user", user_text)
        if self.llm is None:
            reply = self._finish_fallback(conversation, trace, prefix="", committed=False)
            trace.total_ms = _elapsed(started)
            return TurnResult(reply, trace, conversation.pending, _citations(reply))

        messages = conversation.llm_messages()
        try:
            reply = self._model_loop(conversation, messages, trace)
        except LLMTimeout:
            trace.mode = "fallback"
            trace.stage("model_call", "error", "timeout")
            reply = self._finish_fallback(
                conversation,
                trace,
                prefix="The model service timed out, so I used local documents and tools instead.\n\n",
                committed=False,
            )
        except LLMHTTPError as exc:
            trace.mode = "fallback"
            trace.stage("model_call", "error", f"HTTP {exc.status_code}")
            if exc.status_code in {401, 403, 404}:
                prefix = _config_failure_text(exc.status_code) + "\n\n"
            else:
                prefix = "The model service returned an error, so I used local documents and tools instead.\n\n"
            reply = self._finish_fallback(conversation, trace, prefix=prefix, committed=False)
        except LLMError:
            trace.mode = "fallback"
            trace.stage("model_call", "error", "model error")
            reply = self._finish_fallback(
                conversation,
                trace,
                prefix="The model service returned an error, so I used local documents and tools instead.\n\n",
                committed=False,
            )
        trace.total_ms = _elapsed(started)
        return TurnResult(reply, trace, conversation.pending, _citations(reply))

    def commit_pending(
        self,
        conversation: Conversation,
        *,
        trace: Trace | None = None,
        started: float | None = None,
        user_text: str | None = None,
    ) -> TurnResult:
        started = time.perf_counter() if started is None else started
        trace = trace or Trace(turn_id=f"turn-{uuid.uuid4().hex[:8]}", mode="confirm")
        pending = conversation.pending
        if pending is None:
            reply = "There is no ticket draft to submit."
            if user_text:
                conversation.add("user", user_text)
            conversation.add("assistant", reply)
            trace.stage("confirmation_gate", "nothing_pending", "No write was attempted.")
            trace.total_ms = _elapsed(started)
            return TurnResult(reply, trace, None)
        try:
            ticket = self._write(pending)
        except Exception as exc:  # noqa: BLE001 - keep the draft when the write fails
            reply = f"I could not save the ticket ({type(exc).__name__}). The draft is still waiting for confirmation."
            if user_text:
                conversation.add("user", user_text)
            conversation.add("assistant", reply)
            trace.stage("confirmation_gate", "error", type(exc).__name__)
            trace.total_ms = _elapsed(started)
            return TurnResult(reply, trace, pending)
        conversation.pending = None
        if pending.action == "create":
            reply = (
                f"Confirmed. I created ticket {ticket.id} with priority {ticket.priority} and status {ticket.status}. "
                "You can review it on the Tickets page."
            )
        else:
            reply = (
                f"Confirmed. I updated ticket {ticket.id}. Priority is {ticket.priority} and status is {ticket.status}."
            )
        if user_text:
            conversation.add("user", user_text)
        reply = _with_actions(reply, trace, committed=True)
        conversation.add("assistant", reply)
        trace.stage("confirmation_gate", "committed", ticket.id)
        trace.total_ms = _elapsed(started)
        return TurnResult(reply, trace, None)

    def cancel_pending(
        self,
        conversation: Conversation,
        *,
        trace: Trace | None = None,
        started: float | None = None,
        user_text: str | None = None,
    ) -> TurnResult:
        started = time.perf_counter() if started is None else started
        trace = trace or Trace(turn_id=f"turn-{uuid.uuid4().hex[:8]}", mode="confirm")
        conversation.pending = None
        reply = "Canceled. I did not create or update a ticket."
        if user_text:
            conversation.add("user", user_text)
        conversation.add("assistant", reply)
        trace.stage("confirmation_gate", "canceled", "Proposal dropped. No database write.")
        trace.total_ms = _elapsed(started)
        return TurnResult(reply, trace, None)

    def _model_loop(self, conversation: Conversation, messages: list, trace: Trace) -> str:
        for _step in range(self.max_steps):
            response = self.llm.complete(
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=TOOL_SCHEMAS,
            )
            tool_names = [call.name for call in response.tool_calls]
            trace.stage(
                "model_call",
                response.stop_reason,
                "tools=" + (",".join(tool_names) if tool_names else "none"),
                latency_ms=response.latency_ms,
            )
            if not response.tool_calls:
                return self._finalize_answer(conversation, trace, response.text, committed=False)
            messages.append({"role": "assistant", "content": response.public_content})
            results = []
            for call in response.tool_calls:
                result = self.tools.execute(call.name, call.arguments, conversation)
                trace.stage(
                    "tool_call",
                    result.outcome,
                    result.summary,
                    tool=call.name,
                    args=result.safe_args,
                )
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": result.model_text,
                        "is_error": result.outcome != "success",
                    }
                )
            messages.append({"role": "user", "content": results})
        trace.stage("agent_loop", "max_steps", "Stopped after the allowed number of model calls.")
        summary = _tool_summary(trace)
        text = (
            "I stopped after the maximum number of steps so this turn cannot loop. "
            f"Here is what the tools already returned: {summary}"
        )
        text = _with_actions(text, trace, committed=False)
        conversation.add("assistant", text)
        return text

    def _finalize_answer(self, conversation: Conversation, trace: Trace, text: str, *, committed: bool) -> str:
        answer = (text or "").strip() or "I need the device and the exact error before I can suggest a next step."
        grounding = check_grounding(answer, conversation.last_retrieved_ids)
        trace.stage("grounding", grounding.outcome, grounding.detail)
        answer = guard_ticket_claims(grounding.text, committed=committed)
        if grounding.outcome == "uncited":
            answer += "\n\nI retrieved documents on this turn but did not keep a passage citation in the reply."
        answer = _with_actions(answer, trace, committed=committed)
        conversation.add("assistant", answer)
        return answer

    def _finish_fallback(self, conversation: Conversation, trace: Trace, *, prefix: str, committed: bool) -> str:
        body = self.fallback.run(conversation, trace)
        body = guard_ticket_claims(body, committed=committed)
        reply = prefix + _with_actions(body, trace, committed=committed)
        conversation.add("assistant", reply)
        return reply

    def _write(self, pending: TicketProposal):
        if pending.action == "update":
            if not pending.ticket_id:
                raise KeyError("missing ticket id")
            fields = dict(pending.updates)
            if not fields:
                raise ValueError("Update proposal has no fields.")
            return self.database.update_ticket(pending.ticket_id, fields, detail=pending.proposal_id)
        return self.database.create_ticket(
            requester=pending.requester,
            category=pending.category,
            priority=pending.priority,
            service=pending.service,
            summary=pending.summary,
            description=pending.description,
            detail=pending.proposal_id,
        )


def explain_actions(trace: Trace, *, committed: bool) -> str:
    reasons = {
        "search_knowledge": "to ground the steps in Northstar documents",
        "check_service_status": "to see whether this is a known incident",
        "propose_ticket": "to prepare a ticket without submitting it",
        "propose_ticket_update": "to prepare a ticket change without writing it",
    }
    bits = []
    for stage in trace.stages:
        if stage.get("stage") != "tool_call":
            continue
        tool = stage.get("tool")
        if stage.get("outcome") == "success" and tool in reasons:
            bits.append(f"I used {tool} {reasons[tool]}.")
        elif stage.get("outcome") != "success" and tool:
            bits.append(f"{tool} returned {stage.get('outcome')}.")
    if committed:
        bits.append("You confirmed the draft, so I wrote it to the local ticket database.")
    elif any(stage.get("tool") == "propose_ticket" and stage.get("outcome") == "success" for stage in trace.stages):
        bits.append("I did not write the ticket because you have not confirmed it.")
    if not bits:
        if any(stage.get("stage") == "route" and stage.get("outcome") == "direct" for stage in trace.stages):
            return "What I did: I answered directly because the message did not describe an IT system."
        return "What I did: I answered from this turn without a successful tool call."
    return "What I did: " + " ".join(bits)


def _with_actions(text: str, trace: Trace, *, committed: bool) -> str:
    note = explain_actions(trace, committed=committed)
    if "What I did:" in text:
        return text
    return f"{text.rstrip()}\n\n{note}"


def _tool_summary(trace: Trace) -> str:
    parts = [
        f"{stage.get('tool')} ({stage.get('outcome')})"
        for stage in trace.stages
        if stage.get("stage") == "tool_call"
    ]
    return ", ".join(parts) if parts else "no tool results"


def _config_failure_text(status_code: int) -> str:
    if status_code == 401:
        return "The model rejected the credentials in the environment (HTTP 401). Check the endpoint, key, and model name."
    if status_code == 403:
        return "The model refused the request (HTTP 403). Check the endpoint and key permissions."
    return "The model endpoint was not found (HTTP 404). AZURE_CLAUDE_ENDPOINT should be the full messages URL."


def _citations(text: str) -> list[str]:
    import re

    return re.findall(r"\[(DOC-[A-Z0-9-]+(?:#[a-z0-9-]+)?)\]", text)


def _elapsed(started: float) -> float:
    return (time.perf_counter() - started) * 1000


def trace_has_private_fields(payload: dict) -> bool:
    def walk(value) -> bool:
        if isinstance(value, dict):
            if _PRIVATE_KEYS.intersection(value):
                return True
            return any(walk(item) for item in value.values())
        if isinstance(value, list):
            return any(walk(item) for item in value)
        return False

    return walk(payload)
