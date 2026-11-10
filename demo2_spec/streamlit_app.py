"""Northstar IT Help Desk. UI only: decisions live in the northstar package."""

from __future__ import annotations

import json
import uuid

import streamlit as st

from northstar.eval.harness import run_evaluation
from northstar.models import PRIORITIES, TICKET_STATUSES, Conversation
from northstar.runtime import build_runtime
from northstar.samples import SAMPLE_VPN_QUESTION

st.set_page_config(page_title="Northstar IT Help Desk", page_icon="N", layout="wide")


@st.cache_resource
def get_runtime():
    return build_runtime()


def main() -> None:
    runtime = get_runtime()
    _ensure_session()
    _sidebar(runtime)
    page = st.session_state.page
    if page == "Chat":
        _chat(runtime)
    elif page == "Tickets":
        _tickets(runtime)
    else:
        _evaluation(runtime)


def _ensure_session() -> None:
    if "requester" not in st.session_state:
        st.session_state.requester = "Alex Morgan"
    if "conversation" not in st.session_state:
        st.session_state.conversation = _new_conversation(st.session_state.requester)
    if "page" not in st.session_state:
        st.session_state.page = "Chat"
    if "last_trace" not in st.session_state:
        st.session_state.last_trace = None


def _new_conversation(name: str) -> Conversation:
    return Conversation(id=f"conv-{uuid.uuid4().hex[:8]}", requester=name)


def _sidebar(runtime) -> None:
    st.sidebar.markdown("### Northstar Technologies")
    st.sidebar.caption("Internal IT help desk")
    st.session_state.requester = st.sidebar.text_input("Your name", st.session_state.requester)
    st.session_state.conversation.requester = st.session_state.requester or "Alex Morgan"
    st.session_state.page = st.sidebar.radio("Section", ["Chat", "Tickets", "Evaluation"], index=["Chat", "Tickets", "Evaluation"].index(st.session_state.page))
    if st.sidebar.button("New chat", use_container_width=True):
        st.session_state.conversation = _new_conversation(st.session_state.requester)
        st.session_state.last_trace = None
        st.session_state.page = "Chat"
        st.rerun()
    st.sidebar.markdown("**Simulated service status**")
    st.sidebar.caption("The chat assistant reads this same file through the status tool.")
    for state in runtime.catalog.services.values():
        st.sidebar.markdown(f"**{state.name}**  \n{state.status} — {state.message}")


def _chat(runtime) -> None:
    st.markdown(
        """
        <div style="background:#0E2433;color:#F6F4EF;padding:18px 20px;border-radius:12px;margin-bottom:12px;">
          <div style="letter-spacing:.08em;text-transform:uppercase;font-size:12px;color:#9FD0C6;">Northstar Technologies</div>
          <div style="font-size:28px;font-weight:650;">IT Help Desk</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if runtime.settings.llm_configured:
        st.caption(f"Live model: {runtime.settings.model}. Ticket writes still wait for your confirmation.")
    else:
        st.info(
            "Local mode: no Azure credentials are configured. Answers use the local document search, "
            "the simulated status file, and the same confirmation gate. Add a `.env` file to call Claude."
        )
    conversation = st.session_state.conversation
    for message in conversation.messages:
        with st.chat_message(message.role):
            st.markdown(message.content)
    pending = conversation.pending
    if pending:
        st.warning("This draft is not in the ticket database yet.")
        left, right = st.columns(2)
        left.markdown(f"**{pending.action.title()}** · {pending.priority} · {pending.category}")
        left.write(pending.summary)
        if pending.ticket_id:
            left.caption(f"Existing ticket {pending.ticket_id}")
        if left.button("Confirm", type="primary", use_container_width=True):
            result = runtime.agent.commit_pending(conversation)
            st.session_state.last_trace = result.trace.to_dict()
            st.rerun()
        if right.button("Cancel", use_container_width=True):
            result = runtime.agent.cancel_pending(conversation)
            st.session_state.last_trace = result.trace.to_dict()
            st.rerun()
    if st.button("Try the sample VPN question"):
        st.session_state.queued_prompt = SAMPLE_VPN_QUESTION
        st.rerun()
    typed = st.chat_input("Describe the IT problem")
    queued = st.session_state.pop("queued_prompt", None)
    prompt = queued or typed
    if prompt and prompt.strip():
        result = runtime.agent.handle_message(conversation, prompt.strip())
        st.session_state.last_trace = result.trace.to_dict()
        st.rerun()
    with st.expander("Execution trace", expanded=bool(st.session_state.last_trace)):
        _render_trace(st.session_state.last_trace)


def _tickets(runtime) -> None:
    st.header("Tickets")
    st.caption("Rows appear here only after you confirm a draft. Edits wait for a second confirmation.")
    tickets = runtime.database.list_tickets()
    if not tickets:
        st.info("No tickets yet.")
        return
    labels = [f"{ticket.id} · {ticket.status} · {ticket.priority} · {ticket.summary}" for ticket in tickets]
    selected = st.selectbox("Open a ticket", labels)
    ticket = tickets[labels.index(selected)]
    st.write(
        {
            "id": ticket.id,
            "requester": ticket.requester,
            "category": ticket.category,
            "priority": ticket.priority,
            "service": ticket.service,
            "status": ticket.status,
            "summary": ticket.summary,
            "description": ticket.description,
            "updated_at": ticket.updated_at,
        }
    )
    priority = st.selectbox("New priority", PRIORITIES, index=PRIORITIES.index(ticket.priority))
    status = st.selectbox("New status", TICKET_STATUSES, index=TICKET_STATUSES.index(ticket.status))
    if st.button("Review change"):
        st.session_state.pending_edit = {"id": ticket.id, "priority": priority, "status": status}
    edit = st.session_state.get("pending_edit")
    if edit and edit["id"] == ticket.id and (edit["priority"] != ticket.priority or edit["status"] != ticket.status):
        st.warning(f"Confirm update of {edit['id']} to priority {edit['priority']} and status {edit['status']}.")
        if st.button("Confirm update", type="primary"):
            runtime.database.update_ticket(
                edit["id"],
                {"priority": edit["priority"], "status": edit["status"]},
                detail="confirmed from the tickets page",
            )
            st.session_state.pending_edit = None
            st.rerun()


def _evaluation(runtime) -> None:
    st.header("Evaluation")
    st.caption("This suite uses scripted model replies and local tools. It does not call Azure.")
    if st.button("Run evaluation", type="primary"):
        report = run_evaluation()
        runtime.database.save_eval(report)
        st.session_state.eval_report = report
    report = st.session_state.get("eval_report") or runtime.database.latest_eval()
    if not report:
        st.info("No evaluation run yet.")
        return
    passed, failed, total = report["passed"], report["failed"], report["passed"] + report["failed"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pass rate", f"{report['pass_rate']:.0%}" if report["pass_rate"] <= 1 else str(report["pass_rate"]))
    c2.metric("Cases", f"{passed}/{total}")
    c3.metric("Mean latency", f"{report['mean_latency_ms']:.0f} ms")
    tool_rate = report["tool_success_rate"]
    c4.metric("Tool success", "n/a" if tool_rate is None else f"{tool_rate:.0%}")
    retrieval_rate = report["retrieval_hit_rate"]
    retrieval_label = "n/a" if retrieval_rate is None else f"{retrieval_rate:.0%}"
    st.caption(f"Retrieval hit rate: {retrieval_label}. Failed cases: {failed}.")
    st.dataframe(
        [
            {
                "case": item["id"],
                "result": "pass" if item["passed"] else "fail",
                "latency_ms": item["latency_ms"],
                "tools": f"{item['tool_successes']}/{item['tool_total']}",
                "requirements": ", ".join(item["requirement_ids"]),
                "note": item["note"],
            }
            for item in report["results"]
        ],
        use_container_width=True,
        hide_index=True,
    )


def _render_trace(trace: dict | None) -> None:
    if not trace:
        st.caption("Send a message to see the stages and tool calls for that turn.")
        return
    st.caption(f"{trace['turn_id']} · {trace['mode']} · {trace['total_ms']:.0f} ms")
    for stage in trace["stages"]:
        tool = f" · {stage['tool']}" if stage.get("tool") else ""
        st.markdown(f"**{stage['stage']}{tool}** — {stage['outcome']}")
        if stage.get("detail"):
            st.caption(stage["detail"])
        if stage.get("args"):
            st.code(json.dumps(stage["args"], indent=2), language="json")


main()
