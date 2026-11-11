"""Reproducible evaluation used by pytest and the dashboard. FR-EVAL-01, FR-EVAL-02."""

from __future__ import annotations

import json
import tempfile
import time
import uuid
from pathlib import Path

from northstar.agent.loop import trace_has_private_fields
from northstar.config import PACKAGE_ROOT, Settings
from northstar.llm.client import LLMTimeout, MockLLMClient
from northstar.models import Conversation
from northstar.rag.retriever import KnowledgeBase
from northstar.runtime import build_runtime

CASES_PATH = Path(__file__).with_name("cases.json")


def load_cases(path: Path | None = None) -> list[dict]:
    return json.loads((path or CASES_PATH).read_text(encoding="utf-8"))


def run_evaluation(cases: list[dict] | None = None) -> dict:
    selected = cases if cases is not None else load_cases()
    results = [run_case(case) for case in selected]
    latencies = [item["latency_ms"] for item in results]
    tool_ok = sum(item["tool_successes"] for item in results)
    tool_total = sum(item["tool_total"] for item in results)
    retrieval = [item for item in results if item["kind"] == "retrieval" and item.get("scored_retrieval")]
    hits = [item for item in retrieval if item["retrieval_hit"]]
    covered = set()
    for item in results:
        if item["passed"]:
            covered.update(item["requirement_ids"])
    return {
        "id": f"eval-{uuid.uuid4().hex[:8]}",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": results,
        "passed": sum(1 for item in results if item["passed"]),
        "failed": sum(1 for item in results if not item["passed"]),
        "pass_rate": _ratio(sum(1 for item in results if item["passed"]), len(results)),
        "mean_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else 0,
        "tool_success_rate": None if tool_total == 0 else round(tool_ok / tool_total, 3),
        "retrieval_hit_rate": None if not retrieval else round(len(hits) / len(retrieval), 3),
        "requirement_ids_passed": sorted(covered),
    }


def run_case(case: dict) -> dict:
    started = time.perf_counter()
    notes: list[str] = []
    tool_successes = 0
    tool_total = 0
    retrieval_hit = False
    scored_retrieval = False
    kind = case["kind"]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        if kind == "retrieval":
            knowledge = KnowledgeBase(PACKAGE_ROOT / "knowledge")
            found = knowledge.search(case.get("query") or "", top_k=3)
            if case.get("expect_empty"):
                scored_retrieval = True
                retrieval_hit = not found
                if found:
                    notes.append(f"expected no passages, got {[item.passage_id for item in found]}")
            if case.get("expect_doc"):
                scored_retrieval = True
                retrieval_hit = any(item.document_id == case["expect_doc"] for item in found)
                if not retrieval_hit:
                    notes.append(
                        f"expected {case['expect_doc']} in {[item.passage_id for item in found] or ['<empty>']}"
                    )
        else:
            settings = _temp_settings(Path(temp_dir))
            llm = None
            if kind == "agent_timeout":
                llm = _TimeoutClient()
            elif kind in {"agent_mock", "agent_memory", "security"} and case.get("script") is not None:
                llm = MockLLMClient(case.get("script"))
            elif kind == "agent_mock":
                llm = MockLLMClient(case.get("script"))
            elif kind == "agent_memory":
                llm = MockLLMClient(case.get("script"))
            elif kind == "security" and case.get("expect_blocked"):
                llm = MockLLMClient([{"stop_reason": "end_turn", "text": "should not be called"}])
            runtime = build_runtime(settings, llm=llm, force_local=llm is None)
            conversation = Conversation(id="eval", requester="Eval User")
            result = None
            if kind == "agent_memory":
                for turn in case["turns"]:
                    result = runtime.agent.handle_message(conversation, turn)
                second_call = llm.calls[1]["messages"]
                blob = json.dumps(second_call)
                if case["turns"][0] not in blob:
                    notes.append("second model call did not include the first user turn")
            else:
                result = runtime.agent.handle_message(conversation, case["user"])
            assert result is not None
            trace = result.trace.to_dict()
            tool_stages = [stage for stage in trace["stages"] if stage.get("stage") == "tool_call"]
            tool_total = len(tool_stages)
            tool_successes = sum(1 for stage in tool_stages if stage.get("outcome") == "success")
            if "expect_tools" in case:
                actual = [stage.get("tool") for stage in tool_stages]
                for name in case["expect_tools"]:
                    if name not in actual:
                        notes.append(f"missing tool {name}; saw {actual}")
                if case["expect_tools"] == [] and actual:
                    notes.append(f"expected no tools, saw {actual}")
            if case.get("expect_blocked"):
                if not any(stage.get("stage") == "input_screen" and stage.get("outcome") == "blocked" for stage in trace["stages"]):
                    notes.append("injection was not blocked")
                if isinstance(llm, MockLLMClient) and llm.calls:
                    notes.append("blocked turn still called the model")
            if case.get("expect_blocked") is False:
                if any(stage.get("outcome") == "blocked" for stage in trace["stages"]):
                    notes.append("a normal IT message was blocked")
            if "expect_ticket_count" in case and runtime.database.count_tickets() != case["expect_ticket_count"]:
                notes.append(f"ticket count {runtime.database.count_tickets()} != {case['expect_ticket_count']}")
            if case.get("expect_pending") and result.pending is None:
                notes.append("expected a pending ticket draft")
            if case.get("expect_priority") and (result.pending is None or result.pending.priority != case["expect_priority"]):
                notes.append(f"pending priority was {getattr(result.pending, 'priority', None)}")
            if case.get("expect_question") and "?" not in result.message:
                notes.append("expected a clarifying question")
            if case.get("expect_status_word") and case["expect_status_word"] not in result.message.lower():
                notes.append(f"answer did not include status word {case['expect_status_word']}")
            if case.get("expect_citation_grounded"):
                grounding = next((stage for stage in trace["stages"] if stage.get("stage") == "grounding"), None)
                if grounding is None or grounding.get("outcome") != "supported":
                    notes.append(f"grounding was {None if grounding is None else grounding.get('outcome')}")
            if case.get("expect_grounding"):
                grounding = next((stage for stage in trace["stages"] if stage.get("stage") == "grounding"), None)
                actual = None if grounding is None else grounding.get("outcome")
                if actual != case["expect_grounding"]:
                    notes.append(f"grounding {actual} != {case['expect_grounding']}")
            if case.get("expect_no_private_trace") and trace_has_private_fields(trace):
                notes.append("trace exposed private reasoning fields")
            if case.get("expect_model_calls") is not None and len(llm.calls) != case["expect_model_calls"]:
                notes.append(f"model calls {len(llm.calls)} != {case['expect_model_calls']}")
            if case.get("expect_max_steps"):
                if not any(stage.get("stage") == "agent_loop" and stage.get("outcome") == "max_steps" for stage in trace["stages"]):
                    notes.append("loop did not stop at the step limit")
            for snippet in case.get("expect_text") or []:
                if snippet.lower() not in result.message.lower() and snippet not in result.message:
                    notes.append(f"answer missing {snippet!r}")
            for snippet in case.get("forbid_text") or []:
                if snippet in result.message:
                    notes.append(f"answer still contains {snippet!r}")
            if "What I did:" not in result.message and kind == "fallback" and case.get("expect_tools"):
                notes.append("answer did not explain the actions")
    return {
        "id": case["id"],
        "kind": kind,
        "requirement_ids": case.get("requirement_ids", []),
        "passed": not notes,
        "note": "; ".join(notes) if notes else "Passed.",
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "tool_successes": tool_successes,
        "tool_total": tool_total,
        "retrieval_hit": retrieval_hit,
        "scored_retrieval": scored_retrieval,
    }


class _TimeoutClient:
    def complete(self, **kwargs):
        del kwargs
        raise LLMTimeout("timed out")


def _temp_settings(temp_dir: Path) -> Settings:
    return Settings(
        endpoint=None,
        api_key=None,
        model=None,
        api_version="2023-06-01",
        auth_style="api-key",
        db_path=temp_dir / "helpdesk.db",
        knowledge_dir=PACKAGE_ROOT / "knowledge",
        status_path=PACKAGE_ROOT / "data" / "service_status.json",
        timeout_s=5,
        max_steps=4,
    )


def _ratio(part: int, whole: int) -> float:
    if whole == 0:
        return 0.0
    return round(part / whole, 3)
