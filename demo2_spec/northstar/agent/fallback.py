"""Deterministic local responder. FR-AGENT-01, FR-CHAT-03, FR-OPS-01."""

from __future__ import annotations

import re

from northstar.agent.grounding import check_grounding
from northstar.models import SERVICE_CATEGORY, Conversation, Passage, Trace
from northstar.tools.registry import ToolRegistry

_SERVICE_PATTERNS = (
    ("vpn", ("vpn", "globalprotect", "global protect")),
    ("email", ("outlook", "mailbox", "email")),
    ("wifi", ("wi-fi", "wifi", "wireless")),
    ("m365", ("teams", "sharepoint", "onedrive", "microsoft 365", "office 365")),
    ("zoom", ("zoom", "video call")),
    ("endpoint", ("laptop", "blue screen", "bitlocker", "endpoint")),
    ("printing", ("printer", "printing")),
    ("sso", ("sso", "single sign-on", "okta", "can't log in", "cannot log in", "login")),
)
_IT_WORDS = (
    "vpn",
    "email",
    "outlook",
    "wifi",
    "wi-fi",
    "laptop",
    "zoom",
    "password",
    "printer",
    "ticket",
    "login",
    "teams",
    "globalprotect",
)
_URGENT = re.compile(
    r"(?i)\b(urgent|asap|presentation|client meeting|within\s+\d+\s+minutes?|\d+\s+minutes?)\b"
)
_WANTS_TICKET = re.compile(r"(?i)\b(create|open|file|draft|escalate)\b.{0,30}\bticket\b|\bticket\b")
_DEVICE = re.compile(r"(?i)\b(windows|macos|mac os|linux|globalprotect|iphone|android)\b")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


class FallbackAgent:
    def __init__(self, tools: ToolRegistry):
        self.tools = tools

    def run(self, conversation: Conversation, trace: Trace) -> str:
        query = " ".join(message.content for message in conversation.messages if message.role == "user")[-1500:]
        if not _looks_like_it(query):
            trace.stage("route", "direct", "No IT subject. Answered without tools.")
            return (
                "I can help with Northstar IT issues such as VPN, email, Wi-Fi, laptops, meetings, and passwords. "
                "What is going wrong?"
            )

        trace.stage("route", "fallback", "Local responder selected document search and, when a service is named, status.")
        search = self.tools.execute("search_knowledge", {"query": query, "top_k": 3}, conversation)
        trace.stage(
            "tool_call",
            search.outcome,
            search.summary,
            tool="search_knowledge",
            args=search.safe_args,
        )
        service = detect_service(query)
        status_payload = None
        if service:
            status = self.tools.execute("check_service_status", {"service": service}, conversation)
            trace.stage(
                "tool_call",
                status.outcome,
                status.summary,
                tool="check_service_status",
                args=status.safe_args,
            )
            if status.outcome == "success":
                status_payload = _json_obj(status.model_text)

        urgent = bool(_URGENT.search(query))
        wants_ticket = bool(_WANTS_TICKET.search(query))
        if (urgent or wants_ticket) and conversation.last_passages:
            proposal_args = _draft_args(conversation, service, urgent)
            proposed = self.tools.execute("propose_ticket", proposal_args, conversation)
            trace.stage(
                "tool_call",
                proposed.outcome,
                proposed.summary,
                tool="propose_ticket",
                args=proposed.safe_args,
            )

        answer = _compose(conversation, status_payload, urgent, query)
        grounding = check_grounding(answer, conversation.last_retrieved_ids)
        trace.stage("grounding", grounding.outcome, grounding.detail)
        return grounding.text


def detect_service(text: str) -> str | None:
    lowered = text.lower()
    for service, words in _SERVICE_PATTERNS:
        if any(word in lowered for word in words):
            return service
    return None


def _looks_like_it(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in _IT_WORDS)


def _compose(conversation: Conversation, status_payload: dict | None, urgent: bool, query: str) -> str:
    lines = ["I checked the local IT documents before suggesting steps."]
    if status_payload:
        lines.append(
            f"Service status for {status_payload['name']}: **{status_payload['status']}**. "
            f"{status_payload['message']} This line is from the status tool, not a policy citation."
        )
    quotes = _supporting_sentences(conversation.last_passages, query, limit=3)
    if quotes:
        lines.append("Steps and policy from the documents:")
        lines.extend(f"- {sentence} [{passage.passage_id}]" for sentence, passage in quotes)
    else:
        lines.append(
            "I could not find a matching procedure. Which system is this about: VPN, email, Wi-Fi, laptop, meetings, or passwords?"
        )
    latest = conversation.messages[-1].content if conversation.messages else ""
    if not _DEVICE.search(latest) and detect_service(latest) == "vpn":
        lines.append("Which device are you using, Windows or macOS, and is the client GlobalProtect?")
    if urgent and quotes:
        lines.append("Because the meeting is soon, use the workaround in the documents before any reinstall.")
    if conversation.pending and conversation.pending.action == "create":
        pending = conversation.pending
        lines.append(
            f"I drafted an {pending.priority} ticket: \"{pending.summary}\". "
            "It is not created yet. Choose Confirm to submit it or Cancel to drop it."
        )
    return "\n\n".join(lines)


_QUERY_STOP = {
    "a",
    "an",
    "and",
    "am",
    "are",
    "can",
    "for",
    "have",
    "i",
    "in",
    "is",
    "it",
    "my",
    "of",
    "on",
    "or",
    "the",
    "to",
    "you",
}


def _supporting_sentences(passages: list[Passage], query: str, limit: int) -> list[tuple[str, Passage]]:
    """Pick retrieved sentences that answer the question, not the sentence that only repeats it."""
    query_terms = set(re.findall(r"[a-z0-9]+", query.lower())) - _QUERY_STOP
    scored: list[tuple[int, str, Passage]] = []
    for passage in passages:
        best_sentence = ""
        best_score = -1
        for sentence in _SENTENCE.split(passage.text.strip()):
            sentence = sentence.strip()
            if len(sentence) < 40:
                continue
            score = _sentence_score(sentence, query_terms)
            if score > best_score:
                best_sentence = sentence
                best_score = score
        if best_sentence:
            scored.append((best_score, best_sentence, passage))
    scored.sort(key=lambda item: (-item[0], item[2].passage_id))
    if any(score >= 4 for score, _, _ in scored):
        scored = [item for item in scored if item[0] >= 4]
    return [(sentence, passage) for _, sentence, passage in scored[:limit]]


def _sentence_score(sentence: str, query_terms: set[str]) -> int:
    lowered = sentence.lower()
    terms = set(re.findall(r"[a-z0-9]+", lowered))
    score = len(terms & query_terms)
    for phrase, weight in (
        ("us-central", 4),
        ("sign out", 3),
        ("hotspot", 3),
        ("gateway", 2),
        ("reconnect", 2),
    ):
        if phrase in lowered:
            score += weight
    if lowered.startswith("employees report"):
        score -= 3
    return score


def _draft_args(conversation: Conversation, service: str | None, urgent: bool) -> dict:
    latest = next((message.content for message in reversed(conversation.messages) if message.role == "user"), "")
    summary_body = re.sub(r"\s+", " ", latest).strip()
    prefix = f"{(service or 'IT').upper()} issue: "
    summary = prefix + _clip(summary_body, 120 - len(prefix))
    if len(summary) < 5:
        summary = "Employee IT issue"
    description = (
        f"{latest.strip()}\n\nDrafted from the chat after documents and service status were checked. "
        "No password or key was collected."
    )
    return {
        "summary": summary,
        "description": description[:2000],
        "category": SERVICE_CATEGORY.get(service or "", "other"),
        "priority": "urgent" if urgent else "medium",
        "service": service,
    }


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(".,;:")
    return (cut or text[: limit - 1]) + "…"


def _json_obj(text: str) -> dict | None:
    import json

    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None
