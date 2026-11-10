# Implementation plan

Implement `demo2_spec/` in this order. Each milestone is independently testable. Do not start a milestone by weakening a requirement; if a requirement cannot be met, update this specification first and record the change in `specs/review.md`.

Demo 1 is not part of these milestones. It is a separate vibe-coded tree that must not import `northstar`.

## Milestone 1 — Skeleton, settings, database, corpus

Requirements: `FR-RAG-01`, `FR-DATA-01`, `FR-SEC-03`, `NFR-01`, `NFR-03`.

- Package layout from `architecture.md`.
- `Settings` loads Azure variables and redacts the key.
- SQLite schema for tickets, ticket events, and eval runs.
- Knowledge markdown and `service_status.json`.
- `.env.example` and `.gitignore`.

Tests: corpus ids load; a ticket inserted through the database helper is visible from a new connection; settings repr hides the key.

Exit: `pytest` for milestone 1 modules passes without network.

## Milestone 2 — Retrieval

Requirements: `FR-RAG-02`.

- Heading chunker with stable passage ids.
- TF-IDF cosine search, `top_k` clamped.
- Empty query returns no rows.

Tests: demo utterance hits `DOC-VPN-002`; password utterance hits `DOC-PWD-001`.

## Milestone 3 — Security and confirmation

Requirements: `FR-SEC-01`, `FR-TOOL-03`.

- Injection matcher for user text.
- Passage sanitizer.
- Exact confirm and cancel phrase sets.
- Claim guard for false "I created the ticket" wording. The guard is specified here because it is a pure function with no agent loop yet.

Tests: blocked phrases, allowed normal sentences, poisoned passage placeholder, exact phrase matching.

## Milestone 4 — Tools

Requirements: `FR-TOOL-01`, `FR-TOOL-02`, `FR-SEC-02`.

- Registry with the four tools.
- Status catalog.
- Proposal validation.
- Unknown tool and unknown service errors.

Tests: VPN degraded; unknown service; propose does not insert; invalid proposal; unknown tool rejected.

## Milestone 5 — Agent

Requirements: `FR-CHAT-02`, `FR-CHAT-03`, `FR-CHAT-04`, `FR-RAG-03`, `FR-AGENT-01`, `FR-AGENT-02`, `FR-AGENT-03`, `FR-OPS-01`, `FR-DATA-02`.

- Azure client and mock client.
- Parser drops thinking blocks.
- Bounded loop, memory window, grounding, fallback.
- Timeout path uses fallback and does not insert a ticket.

Tests: scripted search, memory, max steps, timeout, false claim, bad citation, hero fallback, greeting.

## Milestone 6 — Interface

Requirements: `FR-CHAT-01`, `FR-UX-01`, `FR-EVAL-01`, `FR-EVAL-02`.

- Chat page with sample utterance, pending proposal card, and trace.
- Tickets page with staged updates.
- Evaluation page that runs the harness and saves the report.

Tests: AppTest boots the chat page; update helper still requires an explicit update call.

## Milestone 7 — Evaluation suite

Requirements: `FR-EVAL-03` and the case list in `evaluation.md`.

- `cases.json` and harness.
- Dashboard and pytest share that runner.
- Full `pytest` from a clean environment with no `.env`.

Exit: every shipped case passes. Document any spec deviation before changing a test to hide a failure.

## After each milestone

Report:

- requirement ids implemented
- tests passed and failed
- deviations from this specification
- outstanding risks

## Environment the implementation expects

- Python 3.12
- A new virtual environment
- `pip install -r demo2_spec/requirements.txt`
- No system database service
- Azure variables only when a person wants live replies

## Out of plan

- Deploying to a host
- Building a vector index
- Sharing code with `demo1_vibe/`
- Calling the live Claude API from pytest
