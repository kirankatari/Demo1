"""Northstar Technologies IT Help Desk."""

from pathlib import Path

import streamlit as st

from helpdesk.evaluation import run_evaluation
from helpdesk.runtime import HelpDesk
from helpdesk.services import ServiceCatalog
from helpdesk.store import (
    CATEGORIES,
    PRIORITIES,
    STATUSES,
    ConfirmationError,
    format_eastern,
    validate_create_draft,
    validate_update_draft,
)

ROOT = Path(__file__).resolve().parent
VPN_SCENARIO = (
    "My VPN keeps disconnecting. I am working remotely, and I have a client "
    "presentation in 30 minutes. Can you help?"
)


@st.cache_resource
def load_desk() -> HelpDesk:
    return HelpDesk.open(ROOT)


def main() -> None:
    st.set_page_config(
        page_title="Northstar IT Help Desk",
        page_icon="◆",
        layout="wide",
    )
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.4rem; max-width: 1080px;}
        div[data-testid="stCaption"] {font-size: 0.95rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    desk = load_desk()
    _ensure_session(desk)
    _sidebar(desk)
    page = st.session_state.page
    if page == "Chat":
        _chat(desk)
    elif page == "Tickets":
        _tickets(desk)
    else:
        _evaluation()


def _ensure_session(desk: HelpDesk) -> None:
    if "requester" not in st.session_state:
        st.session_state.requester = "Alex Chen"
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = desk.store.start_conversation(
            st.session_state.requester
        )
    if "page" not in st.session_state:
        st.session_state.page = "Chat"


def _sidebar(desk: HelpDesk) -> None:
    st.sidebar.markdown("### Northstar Technologies")
    st.sidebar.caption("IT Help Desk")
    st.session_state.page = st.sidebar.radio(
        "Section", ["Chat", "Tickets", "Evaluation"], label_visibility="collapsed"
    )
    requester = st.sidebar.text_input("Your name", st.session_state.requester)
    if requester != st.session_state.requester:
        st.session_state.requester = requester.strip() or "Employee"
        desk.store.set_requester(st.session_state.conversation_id, st.session_state.requester)
    if st.sidebar.button("New conversation", use_container_width=True):
        st.session_state.conversation_id = desk.store.start_conversation(
            st.session_state.requester
        )
        st.rerun()
    if desk.model_configured:
        st.sidebar.success(f"Model: {desk.model_name}")
    else:
        st.sidebar.warning("Azure Claude is not configured. Answers use local documents and simulated status.")
    st.sidebar.markdown("**Service board**")
    catalog = ServiceCatalog(ROOT / "data" / "services.json")
    for service in catalog.list_public():
        st.sidebar.write(f"{service['name']}: {service['status']}")


def _chat(desk: HelpDesk) -> None:
    st.title("IT Help Desk")
    st.caption(
        "Ask in plain language. Document search, service checks, and ticket drafts are logged beside the answer. Tickets are filed only after you confirm."
    )
    if st.button("Try the VPN scenario"):
        desk.agent.handle(
            st.session_state.conversation_id,
            VPN_SCENARIO,
            st.session_state.requester,
        )
        st.rerun()
    _confirmation(desk)
    for message in desk.store.list_messages(st.session_state.conversation_id):
        with st.chat_message("user" if message["role"] == "user" else "assistant"):
            st.markdown(message["content"])
            if message["role"] == "assistant" and message["trace_id"]:
                _trace(desk, message["trace_id"])
    prompt = st.chat_input("Describe the IT problem")
    if prompt:
        desk.agent.handle(
            st.session_state.conversation_id,
            prompt,
            st.session_state.requester,
        )
        st.rerun()


def _trace(desk: HelpDesk, trace_id: int) -> None:
    events = desk.store.get_trace(trace_id)
    with st.expander("What I did and why"):
        if not events:
            st.write("No steps were recorded.")
            return
        for event in events:
            st.markdown(f"**{event['summary']}**")
            st.caption(event["because"])
            detail = event.get("detail") or {}
            if detail:
                st.json(detail, expanded=False)


def _confirmation(desk: HelpDesk) -> None:
    pending = desk.store.get_pending(st.session_state.conversation_id)
    if not pending:
        return
    payload = pending["payload"]
    with st.container(border=True):
        st.markdown("**Confirmation required**")
        st.caption(
            f"This draft expires {format_eastern(pending['expires_at'])}. Nothing is saved until you confirm."
        )
        if pending["action"] == "create":
            st.write(f"{payload['priority']} · {payload['category']} · {payload['requester']}")
            st.subheader(payload["title"], divider=False)
            st.write(payload["description"])
            label = "Create ticket"
        else:
            st.write(f"Ticket {payload['ticket_id']}")
            changes = []
            if "status" in payload:
                changes.append(f"status → {payload['status']}")
            if "priority" in payload:
                changes.append(f"priority → {payload['priority']}")
            st.write(", ".join(changes) or "No fields")
            label = "Apply change"
        confirm, cancel = st.columns(2)
        if confirm.button(label, type="primary", use_container_width=True):
            try:
                outcome = desk.store.confirm(pending["token"])
            except ConfirmationError as exc:
                st.error(str(exc))
            else:
                ticket = outcome["ticket"]
                if outcome["action"] == "create":
                    text = f"Created ticket {ticket['id']} at {ticket['priority']}."
                else:
                    text = (
                        f"Updated ticket {ticket['id']}: status {ticket['status']}, "
                        f"priority {ticket['priority']}."
                    )
                desk.store.add_message(st.session_state.conversation_id, "assistant", text)
                st.rerun()
        if cancel.button("Cancel draft", use_container_width=True):
            try:
                desk.store.cancel(pending["token"])
            except ConfirmationError as exc:
                st.error(str(exc))
            else:
                desk.store.add_message(
                    st.session_state.conversation_id,
                    "assistant",
                    "Cancelled the draft. No ticket was created or changed.",
                )
                st.rerun()


def _tickets(desk: HelpDesk) -> None:
    st.title("Tickets")
    st.caption("SQLite on this machine. Creating or changing a ticket uses the same confirmation card as chat.")
    _confirmation(desk)
    tickets = desk.store.list_tickets()
    if not tickets:
        st.info("No tickets yet. A confirmed draft from chat will show up here.")
    else:
        st.dataframe(
            [
                {
                    "Ticket": ticket["id"],
                    "Priority": ticket["priority"],
                    "Status": ticket["status"],
                    "Category": ticket["category"],
                    "Title": ticket["title"],
                    "Requester": ticket["requester"],
                    "Updated": format_eastern(ticket["updated_at"]),
                }
                for ticket in tickets
            ],
            use_container_width=True,
            hide_index=True,
        )
    _manual_create(desk)
    _manual_update(desk, tickets)


def _manual_create(desk: HelpDesk) -> None:
    with st.expander("Stage a new ticket"):
        with st.form("manual-create"):
            title = st.text_input("Title")
            description = st.text_area("Description")
            category = st.selectbox("Category", sorted(CATEGORIES))
            priority = st.selectbox("Priority", ["P1", "P2", "P3", "P4"], index=2)
            submitted = st.form_submit_button("Review draft")
        if submitted:
            try:
                draft = validate_create_draft(
                    {
                        "title": title,
                        "description": description,
                        "category": category,
                        "priority": priority,
                        "requester": st.session_state.requester,
                    },
                    st.session_state.requester,
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                desk.store.stage(st.session_state.conversation_id, "create", draft)
                st.rerun()


def _manual_update(desk: HelpDesk, tickets: list[dict]) -> None:
    if not tickets:
        return
    with st.expander("Stage a change to an existing ticket"):
        with st.form("manual-update"):
            ticket_id = st.selectbox("Ticket", [ticket["id"] for ticket in tickets])
            status = st.selectbox("New status", sorted(STATUSES))
            priority = st.selectbox("New priority", sorted(PRIORITIES))
            submitted = st.form_submit_button("Review change")
        if submitted:
            try:
                draft = validate_update_draft(
                    {"ticket_id": ticket_id, "status": status, "priority": priority},
                    lambda chosen: bool(desk.store.get_ticket(chosen)),
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                desk.store.stage(st.session_state.conversation_id, "update", draft)
                st.rerun()


def _evaluation() -> None:
    st.title("Evaluation")
    st.caption(
        "Offline cases use a scripted model and the local documents. They do not call Azure. Latency is wall-clock time for each case."
    )
    if st.button("Run offline evaluation", type="primary"):
        st.session_state.eval_report = run_evaluation(ROOT)
    report = st.session_state.get("eval_report")
    if not report:
        st.info("Run the suite to see pass rate, latency, retrieval accuracy, and tool success.")
        return
    first, second, third, fourth = st.columns(4)
    first.metric("Passed", f"{report['passed']}/{report['case_count']}")
    second.metric("Mean latency", f"{report['mean_latency_ms']:.0f} ms")
    third.metric("Retrieval accuracy", f"{report['retrieval_accuracy']:.0%}")
    fourth.metric("Tool success", f"{report['tool_success_rate']:.0%}")
    st.dataframe(
        [
            {
                "Case": case["id"],
                "Result": "Pass" if case["passed"] else "Fail",
                "Kind": case["kind"],
                "Latency ms": case["latency_ms"],
                "Tools ok": f"{case['tools_ok']}/{case['tools_total']}",
                "Coverage": case["coverage"],
                "Detail": case["detail"],
            }
            for case in report["cases"]
        ],
        use_container_width=True,
        hide_index=True,
    )
    failed = [case["id"] for case in report["cases"] if not case["passed"]]
    if failed:
        st.error("Failed: " + ", ".join(failed))
    else:
        st.success("All offline cases passed.")


if __name__ == "__main__":
    main()
else:
    main()
