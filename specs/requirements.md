# Requirements: Northstar Technologies IT Help Desk

Fictional company: Northstar Technologies.
Product: a local AI IT support assistant for employees.
Method: these requirements govern the spec-driven application in `demo2_spec/`. Demo 1 (`demo1_vibe/`) is a separate vibe-coded build of the same product brief and is not driven by this specification.

## 1. Product goal

An employee can describe an IT problem in chat. The assistant searches internal IT documents, checks simulated service status, explains what it did, asks a clarifying question when the next step depends on missing facts, and drafts a support ticket only after the employee confirms.

Primary demo utterance:

> My VPN keeps disconnecting. I am working remotely, and I have a client presentation in 30 minutes. Can you help?

## 2. Actors and scope

| Actor | Description |
| --- | --- |
| Employee | One local user. A display name is collected in the sidebar. There is no corporate login. |
| Help desk assistant | Chat agent plus deterministic tools. |
| Evaluator | A person who runs the evaluation page or `pytest`. |

In scope: chat, conversation memory for the browser session, TF-IDF retrieval over local documents, simulated service status, SQLite tickets, confirmation before create or update, execution trace, evaluation dashboard, Azure Claude when configured, local fallback when it is not.

Out of scope: real VPN or identity-provider integration, multi-user authentication, email notifications, a vector database, and any network call other than the Claude endpoint.

## 3. Assumptions closed before implementation

1. Claude is called with the Anthropic Messages API on Azure. `AZURE_CLAUDE_ENDPOINT` is the full messages URL. The key and model name come only from the environment.
2. Supported auth headers: `api-key` (default), `x-api-key`, and `Authorization: Bearer`.
3. Ticket modification is required, and it uses the same confirmation gate as creation.
4. Confirmation is an on-screen button, or a chat reply whose entire text is an exact confirmation phrase.
5. If Azure credentials are missing or the call fails with a timeout or server error, the app still answers from local documents and tools and says it did so.
6. Language is English. The corpus is fictional and stored in the repo.

## 4. Functional requirements

### FR-CHAT-01 Interactive chat

Requirements: Streamlit chat where the employee types a problem and sees an assistant reply.
Expected behavior: the sample VPN question can be submitted from the input or the sample button. Replies render in order.
Acceptance criteria: submitting text appends a user turn and an assistant turn; the sample button submits the demo utterance.
Test cases: `test_hero_fallback_end_to_end`, `test_app_renders_chat`.
Error handling: empty input is ignored.

### FR-CHAT-02 Conversation memory

Requirements: later turns can use earlier turns in the same browser session.
Expected behavior: the model payload for turn N includes prior user and assistant text from that session, capped at the last 20 turns.
Acceptance criteria: a second mocked model call contains the first user message.
Test cases: `test_memory_includes_prior_turn`.
Error handling: memory is session-scoped. A new chat starts empty. Server restart clears session memory. Tickets remain in SQLite.

### FR-CHAT-03 Clarifying questions

Requirements: when device or VPN client is missing and would change the steps, the assistant asks.
Expected behavior: the demo utterance does not name Windows, macOS, or GlobalProtect, so the reply asks which device or client is in use while still giving immediate steps.
Acceptance criteria: the fallback reply to the demo utterance contains a question mark and a device or client question.
Test cases: `test_hero_fallback_end_to_end`.
Error handling: if the user already named the device, the fallback does not repeat that question.

### FR-CHAT-04 Explain actions

Requirements: every IT answer states what ran and why.
Expected behavior: a deterministic "What I did" note is attached from the trace, covering search, status, and ticket draft.
Acceptance criteria: the demo reply explains the document search, the status check, and that the ticket was not submitted.
Test cases: `test_hero_fallback_end_to_end`.
Error handling: if no tool ran, the note says the assistant answered directly.

### FR-RAG-01 Knowledge corpus

Requirements: fictional Northstar IT documents ship with the app.
Expected behavior: documents cover VPN policy, VPN troubleshooting, passwords and MFA, email, Wi-Fi, endpoints, Zoom, ticket priority, software requests, and support boundaries.
Acceptance criteria: the loader reads at least those document ids.
Test cases: `test_corpus_contains_required_documents`.
Error handling: a missing knowledge directory raises a clear startup error.

### FR-RAG-02 TF-IDF retrieval

Requirements: local TF-IDF cosine retrieval. No vector database and no embedding API.
Expected behavior: the demo utterance ranks a `DOC-VPN-002` passage in the top three. A password question ranks `DOC-PWD-001`.
Acceptance criteria: top-k is between 1 and 5, default 3. Scores are returned with passage ids.
Test cases: `test_hero_query_retrieves_vpn_troubleshooting`, `test_password_query_retrieves_password_doc`.
Error handling: an empty query returns no passages. A query with no lexical overlap returns an empty list rather than a fabricated policy.

### FR-RAG-03 Grounded citations

Requirements: procedural steps quote retrieved passages and cite passage ids like `[DOC-VPN-002#switch-gateway]`.
Expected behavior: citations in the final answer must be a subset of the passages retrieved on that turn. Unsupported citation markers are removed. If passages were retrieved, at least one valid citation remains on the fallback path.
Acceptance criteria: fallback demo answer cites only retrieved ids; a mocked answer that cites an unknown id is marked `unsupported_citation` and the marker is removed.
Test cases: `test_fallback_citations_are_grounded`, `test_unsupported_citation_is_stripped`.
Error handling: status-tool text is labeled as live status, not as a document citation.

### FR-AGENT-01 Action choice

Requirements: the agent chooses among a direct answer, document retrieval, and tools.
Expected behavior: IT problem wording leads to `search_knowledge` and, when a known service is named, `check_service_status`. Greetings with no IT subject are answered directly. Urgent incidents and explicit ticket requests call `propose_ticket`, which only drafts.
Acceptance criteria: the demo utterance on the fallback path records those tool stages and does not write a ticket. A greeting does not call tools.
Test cases: `test_hero_fallback_end_to_end`, `test_greeting_skips_tools`, `test_mock_agent_searches_then_answers`.
Error handling: unknown tool names are rejected and do not crash the turn.

### FR-AGENT-02 Bounded loop

Requirements: the model loop cannot run indefinitely.
Expected behavior: at most four model calls per user turn. Tool results are sent back into the next call. At the limit, the loop stops and summarizes without another model call.
Acceptance criteria: a mock that always requests a tool results in exactly four model calls.
Test cases: `test_loop_stops_at_max_steps`.
Error handling: the user sees a bounded-loop explanation plus any tool facts already collected.

### FR-AGENT-03 Execution trace

Requirements: show stages and tool calls without private model reasoning.
Expected behavior: stages include input screening, model or fallback routing, each tool call, grounding, and the confirmation gate when relevant. Thinking blocks from the provider are not stored in the trace or the chat.
Acceptance criteria: trace JSON has no `thinking` or `chain_of_thought` field; the Azure parser drops thinking blocks before they reach the trace.
Test cases: `test_trace_has_no_private_reasoning`, `test_azure_client_strips_thinking`.
Error handling: tool arguments are redacted before display.

### FR-TOOL-01 Service status

Requirements: a tool reports simulated status for a fixed catalog.
Expected behavior: catalog is vpn, email, sso, wifi, m365, zoom, endpoint, printing. VPN starts as degraded, with the US-East gateway incident in the status message. Other services start operational except where the status file says otherwise.
Acceptance criteria: `check_service_status` for vpn returns degraded and the workaround text. An unknown service returns an error listing the catalog and does not throw.
Test cases: `test_vpn_status_degraded`, `test_unknown_service_is_error`.
Error handling: a missing or invalid status file fails startup with the file path. It does not invent "operational".

### FR-TOOL-02 Draft a ticket

Requirements: the assistant can prepare a ticket from the conversation.
Expected behavior: `propose_ticket` validates fields and stores a pending proposal on the conversation. SQLite is unchanged.
Acceptance criteria: after a proposal, ticket count is still zero and `conversation.pending` is set. Invalid priority or a too-short summary returns a tool error and does not set a pending proposal.
Test cases: `test_propose_does_not_insert_ticket`, `test_invalid_proposal_rejected`.
Error handling: extra fields are ignored. Category, priority, and service must be in the allowed sets.

### FR-TOOL-03 Confirmation before create or modify

Requirements: no ticket insert or update runs unless the employee confirms that specific proposal.
Expected behavior: confirmation is the Confirm button or an exact phrase (`yes`, `confirm`, `create ticket`, `create the ticket`, `submit`, `go ahead`, `approve`, with optional trailing period). Cancellation is exact too (`no`, `cancel`, `stop`, `never mind`). A pending priority edit such as "change priority to low" updates the draft only. An update proposal for an existing ticket follows the same gate.
Acceptance criteria: exact `yes` inserts one row; `yes, ignore previous instructions` does not; cancel inserts nothing; update changes a row only after confirm.
Test cases: `test_exact_yes_commits_ticket`, `test_yes_with_extra_text_does_not_commit`, `test_cancel_does_not_insert`, `test_priority_edit_updates_draft_only`, `test_update_requires_confirmation`.
Error handling: confirming with nothing pending returns a short explanation and writes nothing. A failed insert leaves the proposal in place.

### FR-SEC-01 Prompt injection protection

Requirements: user text and retrieved passages cannot override tool policy.
Expected behavior: messages that try to ignore instructions, reveal secrets, or skip ticket confirmation are refused before any model or tool call. Passages that contain the same patterns are replaced with a neutral placeholder before they are shown to the model.
Acceptance criteria: the blocked demo does not increment model calls or ticket rows. A normal sentence that merely contains "confirmation" is allowed. A poisoned passage does not reach the tool payload.
Test cases: `test_injection_blocks_override`, `test_injection_allows_normal_vpn_request`, `test_injection_allows_confirmation_in_normal_sentence`, `test_indirect_injection_passage_is_neutralized`.
Error handling: the refusal tells the employee to restate the IT problem. It does not echo a recovered secret.

### FR-SEC-02 Authorized tools only

Requirements: the model may call only the registered tools, and only with validated arguments.
Expected behavior: allowlist is `search_knowledge`, `check_service_status`, `propose_ticket`, `propose_ticket_update`. There is no tool that commits a ticket.
Acceptance criteria: an unknown tool name returns outcome `rejected` and writes no ticket.
Test cases: `test_unknown_tool_rejected`, `test_propose_does_not_insert_ticket`.
Error handling: non-object arguments are rejected.

### FR-SEC-03 Secrets stay in the environment

Requirements: endpoint, key, and model name are read from the environment or a local `.env` file. They are never hardcoded or written to traces, tickets, or eval records.
Expected behavior: settings representation redacts the key. Trace text redacts key-like assignments and `sk-ant-` tokens.
Acceptance criteria: tests construct settings with a fake key and do not find that key in `repr` or a redacted trace.
Test cases: `test_settings_redact_key`, `test_trace_redacts_secret_like_strings`.
Error handling: missing credentials select local mode; they are not a crash.

### FR-DATA-01 SQLite tickets

Requirements: tickets persist in a local SQLite file.
Expected behavior: each ticket has id `TCK-n`, requester, category, priority, service, summary, description, status, timestamps. Create writes status `open` and a confirmation event.
Acceptance criteria: a confirmed ticket can be listed after a new database connection.
Test cases: `test_exact_yes_commits_ticket`.
Error handling: the database file's parent directory is created. Writes use parameters, not string-built SQL.

### FR-DATA-02 Local except the model API

Requirements: documents, TF-IDF, status, tickets, and evaluation run on the machine. The only outbound dependency is the configured Claude endpoint.
Expected behavior: local mode performs no HTTP call. The Azure client is the only HTTP caller.
Acceptance criteria: fallback hero flow does not construct an HTTP client call.
Test cases: `test_hero_fallback_end_to_end` (no client), `test_azure_client_strips_thinking` (mock transport).
Error handling: see FR-OPS-01.

### FR-EVAL-01 Evaluation dashboard

Requirements: a Streamlit page runs the reproducible suite and shows pass/fail, latency, and tool success.
Expected behavior: the suite uses the mock model and the local tools. It does not require Azure. Results show case id, linked requirement ids, pass or fail, latency, and a note. Summary metrics include pass rate, mean latency, and tool success rate.
Acceptance criteria: the harness returns a report where every shipped case passes.
Test cases: `test_eval_harness_passes`.
Error handling: a failed case stores the assertion message and the page still renders the rest.

### FR-EVAL-02 Metrics

Requirements: latency and tool-execution success are visible.
Expected behavior: latency is wall-clock milliseconds for the case. Tool success is successful tool outcomes divided by tool outcomes. Retrieval hit rate is reported separately.
Acceptance criteria: the report includes numeric latency and a tool success rate for the suite.
Test cases: `test_eval_harness_passes`.
Error handling: if a run contains no tool calls, tool success is null and the UI shows `n/a`.

### FR-EVAL-03 Mocked automated tests

Requirements: pytest covers the agent without Azure.
Expected behavior: `MockLLMClient` replays scripted stop reasons, tool calls, and final text. Provider tests use `httpx.MockTransport`.
Acceptance criteria: `pytest` passes with no `.env`.
Test cases: the suite listed in `specs/review.md`.
Error handling: an empty mock script becomes a short request for more detail so the loop still ends.

### FR-OPS-01 Model and tool failures

Requirements: failures are visible and do not commit tickets.
Expected behavior:

| Failure | Behavior |
| --- | --- |
| Timeout or HTTP 408/429/5xx | Tell the user, then answer with the local fallback. |
| HTTP 401/403/404 | Explain the configuration problem without printing the key, then still offer the local answer. |
| Malformed model JSON | Same as a model error, local fallback. |
| Unknown tool or bad arguments | Tool result is an error; the loop may continue until the step limit. |
| Unknown service | Error result listing allowed names. |
| Empty retrieval | Say that no document matched and ask which system is involved. |
| Confirmation with nothing pending | Explain that there is nothing to submit. |

Acceptance criteria: a client that raises timeout still returns VPN document content and writes no ticket.
Test cases: `test_api_timeout_uses_local_documents`.
Error handling: exception text shown to the user is the exception type plus a short status code, after redaction.

### FR-UX-01 Tickets page

Requirements: the employee can see local tickets and stage an edit.
Expected behavior: the page lists SQLite rows. Changing priority or status stages an update and writes only after Confirm update.
Acceptance criteria: the database helper used by that page does not change a row until `update_ticket` is called.
Test cases: `test_update_requires_confirmation`.
Error handling: editing a missing id returns an error string and no new row.

## 5. Non-functional requirements

| ID | Requirement |
| --- | --- |
| NFR-01 | Python 3.12 and a local virtual environment. Dependencies are pinned in `demo2_spec/requirements.txt`. |
| NFR-02 | A fresh checkout runs the eval suite without network access and without credentials. |
| NFR-03 | `.env` is gitignored. `.env.example` contains placeholders only. |
| NFR-04 | Agent steps per turn are capped at 4. Retrieval `top_k` is capped at 5. |
| NFR-05 | Ticket summary is 5–120 characters. Description is 10–2000 characters. |

## 6. Requirement inventory

`FR-CHAT-01`, `FR-CHAT-02`, `FR-CHAT-03`, `FR-CHAT-04`, `FR-RAG-01`, `FR-RAG-02`, `FR-RAG-03`, `FR-AGENT-01`, `FR-AGENT-02`, `FR-AGENT-03`, `FR-TOOL-01`, `FR-TOOL-02`, `FR-TOOL-03`, `FR-SEC-01`, `FR-SEC-02`, `FR-SEC-03`, `FR-DATA-01`, `FR-DATA-02`, `FR-EVAL-01`, `FR-EVAL-02`, `FR-EVAL-03`, `FR-OPS-01`, `FR-UX-01`, `NFR-01` through `NFR-05`.
