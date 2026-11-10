# Implementation plan

Version: 1.0

Implement in the order below. Do not start a milestone by weakening a requirement. If a requirement cannot be met, stop and propose a specification change first.

Each milestone is independently testable. Automated tests use `ScriptedModel` or no model.

## M1 — Skeleton and storage

Build:

- `requirements.txt`, `.gitignore`, `.env.example`, `pytest.ini`, `.streamlit/config.toml`
- `northstar_helpdesk/config.py`
- `northstar_helpdesk/store.py` with the schema in `architecture.md`
- Package init and `runtime.py` wiring the store only as far as tests need

Requirements: FR-OPS-01, FR-OPS-02, FR-DATA-01, FR-SEC-03, FR-SEC-04 (repr and missing-env portion)

Tests: config load, gitignore, quoted title, stage/confirm/cancel/expiry

Exit: those tests pass. No Streamlit yet.

## M2 — Corpus and retrieval

Build:

- The eight markdown files
- `northstar_helpdesk/rag.py`

Requirements: FR-RAG-01, FR-RAG-02, FR-RAG-03 (scorer can land with M6 if the function lives in evaluation; the index itself lands here)

Tests: labeled queries, empty query, corpus file list

Exit: VPN, password, Teams, and guest Wi-Fi rank first.

## M3 — Security

Build:

- `northstar_helpdesk/security.py`

Requirements: FR-SEC-01, FR-SEC-04 (redaction), FR-SEC-05

Tests: VPN story allowed, override blocked, fake tool tag blocked, secret redacted, length 4000 vs 4001

Exit: screen and redact tests pass with no model import.

## M4 — Catalog and draft validation

Build:

- `data/services.json`
- `northstar_helpdesk/services.py`
- create/update validators in `store.py`

Requirements: FR-DATA-02, FR-TOOL-01, FR-TOOL-02, FR-TOOL-03, FR-TOOL-05 (validators)

Tests: aliases, degraded VPN, unknown service, update does not write until confirm

Exit: catalog and validator tests pass.

## M5 — Model client and agent

Build:

- `northstar_helpdesk/model_client.py`
- `northstar_helpdesk/agent.py`
- Fallback, clarifier, citations, trace allowlist, four-round cap

Requirements: FR-AGENT-01 through FR-AGENT-04, FR-CHAT-02, FR-CHAT-03, FR-CHAT-04, FR-RAG-04, FR-TOOL-02 through FR-TOOL-05, FR-SEC-02, FR-OPS-03, FR-OPS-04

Tests: injection does not call the model, user JSON does not create a ticket, memory replay, public trace, Windows clarifier skip

Exit: agent tests pass offline.

## M6 — Evaluation

Build:

- `northstar_helpdesk/evaluation.py` with the case table in `evaluation.md`

Requirements: FR-EVAL-01, FR-EVAL-02, FR-EVAL-03, FR-EVAL-04, FR-EVAL-06, FR-RAG-03

Tests: full suite pass rate 1, latency under 2 seconds per case, tool success recorded below 1, retrieval accuracy 1

Exit: `pytest` green for the suite.

## M7 — Streamlit

Build:

- `app.py` Chat, Tickets, and Evaluation
- Confirmation card bound to `Store.confirm` and `Store.cancel`
- Manual stage forms that still use the card
- Sidebar service board and model-configured warning
- VPN scenario button

Requirements: FR-CHAT-01, FR-EVAL-05, FR-OPS-05

Tests: README mentions the run commands. UI is exercised in a browser against the fallback path and the confirmation card.

Exit: an operator can complete the VPN story without a key, and with a key the same card gates tickets.

## M8 — Full regression

Run the whole `pytest` file. Record passed and failed counts in `specs/milestone-report.md`. Fix code only. Do not edit a requirement to make a failure disappear unless the requirement was wrong; in that case write the proposed change in the milestone report and wait.

## Deviations rule

A deviation is any behavior that contradicts `requirements.md`, `architecture.md`, `agent-design.md`, `security.md`, or `evaluation.md`. Record it in the milestone report with the requirement id. Do not hide it in a comment.

## Environment note

The implementation machine starts without `python3-venv` and without the Azure variables. M1 includes creating a virtual environment after installing the stdlib venv package. Live Claude remains optional through M8.
