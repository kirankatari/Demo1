# Requirements

Product: Northstar Technologies IT Help Desk  
Version: 1.0 (approved for implementation)  
Stack: Python, Streamlit, local TF-IDF, SQLite, Azure Claude

The application helps a fictional employee troubleshoot IT issues. The reference request is: "My VPN keeps disconnecting. I am working remotely, and I have a client presentation in 30 minutes. Can you help?"

Everything except the Claude request stays on the machine. Tests must pass with a mock model and with no `.env` file.

## Actors and assumptions

- One local operator plays the employee. There is no login system.
- The operator's display name defaults to Alex Chen and is editable.
- Service status is simulated. It is not a probe of a real network.
- The Azure deployment name, endpoint, and key are supplied by the operator and are not known at specification time.

## Global acceptance

- `pytest` passes without network access and without Azure credentials.
- Creating or modifying a ticket without `Store.confirm(token)` leaves the `tickets` table unchanged.
- Traces contain `stage`, `summary`, `because`, and `detail` only. They do not contain a reasoning or chain-of-thought field.
- `.env` is gitignored. The API key never appears in trace details, model error text, or `AzureConfig` repr.

---

## FR-CHAT-01 Interactive chat

Requirements  
A Streamlit chat accepts an employee message and shows the assistant reply.

Expected behavior  
The Chat section shows prior turns, a text input, and a one-click VPN scenario. Replies render as chat bubbles.

Acceptance criteria  
- Submitting text adds a user turn and an assistant turn.
- The VPN scenario button submits the reference request.
- Empty input does not call the agent.

Test cases  
- TC-CHAT-01 Conversation rows are persisted and replayed (`test_fr_chat_02_conversation_memory`).
- Manual: Chat, type a greeting, observe a reply bubble.

Error handling  
Storage failures raise `StorageError` with a fixed sentence and do not include SQL or credentials.

## FR-CHAT-02 Conversation memory

Requirements  
Later turns can see earlier user and assistant text from the same conversation.

Expected behavior  
The agent loads the last 12 plain-text messages before calling the model. Tool protocol from the current turn is not written into that history. New conversation starts a new id.

Acceptance criteria  
- The second model call includes the first user message.
- A new conversation does not include the previous conversation's text.

Test cases  
- TC-CHAT-02 `test_fr_chat_02_conversation_memory`
- TC-CHAT-02b evaluation case `CHAT-MEMORY`

Error handling  
A missing conversation id still stores messages. The UI always creates an id first.

## FR-CHAT-03 Explain actions

Requirements  
Each assistant turn can show what ran and why, without private model reasoning.

Expected behavior  
An expander lists trace events. Each event has a fixed summary and a because sentence written by the application.

Acceptance criteria  
- VPN and tool turns have a non-empty trace.
- No event key is `reasoning` or `chain_of_thought`.
- Detail keys belong to the published allowlist.

Test cases  
- TC-CHAT-03 `test_fr_chat_03_trace_is_public`
- TC-CHAT-03b evaluation trace check inside `AGT-VPN`

Error handling  
A missing trace shows "No steps were recorded."

## FR-CHAT-04 Clarifying questions

Requirements  
When a VPN disconnect is reported and the operating system is unknown, the reply asks which operating system Northstar Connect is running on.

Expected behavior  
The question is added by the application if the model text contains no question mark. It is not added when the message already names Windows, macOS, Linux, Ubuntu, or ChromeOS. Urgent workaround text is not withheld while waiting for the answer.

Acceptance criteria  
- The reference VPN prompt produces a reply containing `?`.
- "The VPN keeps disconnecting on Windows" does not gain a second forced question solely because of this rule.

Test cases  
- TC-CHAT-04 evaluation `AGT-VPN` and `AGT-FALLBACK`
- TC-CHAT-04b `test_fr_chat_04_windows_skips_forced_question`

Error handling  
The clarifier is skipped for blocked messages.

---

## FR-RAG-01 Local corpus

Requirements  
Ship fictional Northstar IT documents as markdown on disk.

Expected behavior  
At least the VPN, password/MFA, email/Teams, ticket priority, office Wi-Fi, endpoint, acceptable use, and incident-status documents are present.

Acceptance criteria  
- The knowledge directory contains those eight files.
- An empty directory raises `FileNotFoundError`.

Test cases  
- TC-RAG-01 `test_fr_rag_01_corpus_files`

Error handling  
A missing knowledge directory fails at startup with the directory path. It does not call the model.

## FR-RAG-02 TF-IDF retrieval

Requirements  
Rank document chunks with local TF-IDF cosine similarity. Do not use a vector database.

Expected behavior  
Search returns at most four chunks with score at least 0.08. A hit below 25% of the best score is dropped so a weak neighbor is not cited. Queries shorter than two characters return nothing.

Acceptance criteria  
- The reference VPN wording ranks `vpn-remote-access` first.
- Password, Teams audio, and guest Wi-Fi queries rank `password-mfa`, `email-and-teams`, and `office-wifi` first.

Test cases  
- TC-RAG-02 `test_fr_rag_02_labeled_queries`
- TC-RAG-02b evaluation `RET-VPN`, `RET-PASSWORD`, `RET-TEAMS`, `RET-WIFI`

Error handling  
Low scores are omitted rather than padded with unrelated chunks.

## FR-RAG-03 Grounded recommendations

Requirements  
Troubleshooting text presented as Northstar guidance must come from retrieved chunks or from the service catalog.

Expected behavior  
The offline quality signal is term coverage of the answer body against retrieved excerpts. The VPN scripted answer scores at least 0.25. A reply that does not use those terms scores lower.

Acceptance criteria  
- Coverage is computed after stripping the citation block and the confirmation notice.
- The fallback quotes excerpt text instead of inventing a procedure.

Test cases  
- TC-RAG-03 `test_fr_rag_03_grounding_score`
- TC-RAG-03b `AGT-VPN`, `AGT-FALLBACK`

Error handling  
If nothing clears the score threshold, the reply says no document matched closely.

## FR-RAG-04 Citations

Requirements  
Retrieved documents are cited by title and document id.

Expected behavior  
A `Sources:` block lists each distinct document once. The block is not duplicated if the model already cited every id.

Acceptance criteria  
- A turn that searched `vpn-remote-access` includes that id in the reply.

Test cases  
- TC-RAG-04 evaluation `AGT-VPN` and `AGT-FALLBACK`

Error handling  
No sources block is added when retrieval returns no hits.

---

## FR-AGENT-01 Choose the next action

Requirements  
The model may answer directly, call `search_knowledge_base`, call `check_service_status`, or stage a ticket change.

Expected behavior  
Every model round is offered the four tools. A greeting script that returns text calls none. The application does not force retrieval before the model speaks.

Acceptance criteria  
- The greeting case offers exactly the four tool names and executes none.
- The VPN script executes search and status.

Test cases  
- TC-AGT-01 evaluation `AGT-GREETING` and `AGT-VPN`

Error handling  
Not applicable beyond FR-AGENT-04.

## FR-AGENT-02 Bounded loop

Requirements  
At most four tool rounds run for one employee message.

Expected behavior  
After the fourth tool round the application requests a final answer with tools disabled. Further tool requests are ignored and a summary of collected results is used if needed.

Acceptance criteria  
- A script that always requests search records a `loop_limit` event and creates no ticket.

Test cases  
- TC-AGT-02 evaluation `AGT-LOOP`
- TC-AGT-02b `test_fr_agent_02_loop_bound`

Error handling  
A failure of the final call still returns the summary. It does not start a fifth tool round.

## FR-AGENT-03 Execution trace

Requirements  
Record screening, model response metadata, tool calls, rejections, the loop limit, and fallback use.

Expected behavior  
Model response events store stop reason, tool count, round, and latency. They do not store the model's prose.

Acceptance criteria  
Same as FR-CHAT-03.

Test cases  
- TC-AGT-03 `test_fr_chat_03_trace_is_public`

Error handling  
Unknown detail keys raise `RuntimeError` during development so private fields cannot slip in.

## FR-AGENT-04 Failure recovery

Requirements  
A missing model configuration or a failed model call must still return a useful, bounded reply.

Expected behavior  
The fallback searches the corpus and checks services named in the message. It states that the model is unavailable. It cannot stage or file a ticket.

Acceptance criteria  
- `model is None` on the VPN prompt cites the VPN document, reports degraded status, asks the OS question, and writes no ticket.
- A model that raises `ModelError` takes the same path.

Test cases  
- TC-AGT-04 evaluation `AGT-FALLBACK` and `AGT-MODEL-ERROR`

Error handling  
`ModelError` text is passed through a redactor and truncated to 280 characters.

---

## FR-TOOL-01 Service status

Requirements  
`check_service_status` reads the simulated catalog.

Expected behavior  
Known ids and aliases return name, status, summary, and workaround. Unknown ids return `ok: false` and the valid id list.

Acceptance criteria  
- `vpn` and `Northstar Connect` resolve to the degraded VPN entry.
- `teleporter` does not raise an uncaught exception.

Test cases  
- TC-TOOL-01 `test_fr_tool_01_catalog`
- TC-TOOL-01b evaluation `TOOL-BAD-SERVICE`

Error handling  
A blank `service_id` is a validation error returned to the model as a tool error.

## FR-TOOL-02 Stage ticket creation

Requirements  
`create_support_ticket` inserts a pending action and does not insert a ticket.

Expected behavior  
Required fields: title (8–120), description (20–2000), category, priority. Requester defaults to the display name. The reply says the ticket has not been created.

Acceptance criteria  
- After the tool runs, `ticket_count()` is 0 and a pending create exists.

Test cases  
- TC-TOOL-02 evaluation `AGT-STAGE`
- TC-TOOL-02b `test_fr_tool_02_stage_only`

Error handling  
Invalid fields return `ok: false` and do not stage a draft.

## FR-TOOL-03 Stage ticket modification

Requirements  
`update_support_ticket` stages a status and/or priority change and does not write the ticket row.

Expected behavior  
`ticket_id` must look like `NS-1001` and must exist. At least one of status or priority is required.

Acceptance criteria  
- Priority stays at the old value until confirm.

Test cases  
- TC-TOOL-03 evaluation `AGT-UPDATE`

Error handling  
Unknown ticket ids return a tool error and do not create a pending action.

## FR-TOOL-04 Explicit confirmation

Requirements  
Only `Store.confirm(token)` creates or updates a ticket. The token is not sent to the model.

Expected behavior  
The UI shows the draft and Create/Apply plus Cancel. Cancel marks the draft cancelled. A second confirm fails.

Acceptance criteria  
- Confirm of a create draft yields `NS-1001` for the first ticket.
- Confirm of an update changes only the staged fields.
- Chat text that contains a JSON tool shape does not create a ticket.

Test cases  
- TC-TOOL-04 `test_fr_tool_04_confirm_and_second_confirm`
- TC-TOOL-04b evaluation `AGT-CONFIRM`
- TC-TOOL-04c `test_fr_sec_02_user_json_does_not_create_ticket`

Error handling  
`ConfirmationError` is shown on an expired, cancelled, or unknown token. The tickets table is unchanged.

## FR-TOOL-05 Tool validation

Requirements  
Reject unknown tool names. Validate arguments before side effects.

Expected behavior  
Unknown tools produce `tool_rejected`. Bad arguments produce `tool_error`. Both are returned to the model as `ok: false` so it can answer without crashing.

Acceptance criteria  
- `delete_database` creates no ticket.
- The allowlist is exactly the four published tools.

Test cases  
- TC-TOOL-05 evaluation `TOOL-UNKNOWN` and `TOOL-BAD-SERVICE`

Error handling  
The agent loop continues to a final answer after a rejected tool.

---

## FR-DATA-01 SQLite

Requirements  
Persist conversations, messages, traces, tickets, and pending actions in a local SQLite file.

Expected behavior  
Queries are parameterized. Ticket titles may contain quotes. Pending drafts expire after 30 minutes. A new draft cancels older pending drafts in that conversation.

Acceptance criteria  
- A quoted title round-trips.
- A token older than 30 minutes does not write a ticket.

Test cases  
- TC-DATA-01 `test_fr_data_01_quotes_and_expiry`

Error handling  
`sqlite3.Error` on confirm becomes `StorageError` with a fixed message.

## FR-DATA-02 Simulated catalog

Requirements  
Ship `data/services.json` with vpn, email, teams, sso, wifi, and catalog.

Expected behavior  
VPN status is `degraded` and includes the Backup Gateway workaround. Other listed services are `operational`.

Acceptance criteria  
- Catalog ids match the tool description.

Test cases  
- TC-DATA-02 `test_fr_tool_01_catalog`

Error handling  
Malformed JSON fails at process start. The agent does not invent status.

---

## FR-SEC-01 Prompt-injection screen

Requirements  
Block instruction override, role hijack, prompt extraction, confirmation bypass, and fake tool tags before any model call.

Expected behavior  
The reference VPN story is allowed. "Ignore previous instructions" and "bypass confirmation" are blocked. The model client is not called.

Acceptance criteria  
- Blocked turns create no ticket and record rule `override-instructions`, `role-hijack`, `reveal-prompt`, `skip-confirmation`, `fake-tool`, or `length`.

Test cases  
- TC-SEC-01 `test_fr_sec_01_injection`
- TC-SEC-01b evaluation `SEC-INJECT`

Error handling  
The refusal is a fixed sentence. The original attack text is stored as the user turn so the operator can see it, after secret redaction.

## FR-SEC-02 No direct tool execution from user text

Requirements  
Tools run only from structured model tool calls on the allowlist.

Expected behavior  
A message that merely contains tool JSON is ordinary user text.

Acceptance criteria  
- Ticket count stays 0.

Test cases  
- TC-SEC-02 `test_fr_sec_02_user_json_does_not_create_ticket`

Error handling  
Not applicable.

## FR-SEC-03 Server-side confirmation token

Requirements  
The pending token is generated with `secrets.token_urlsafe` and stored in SQLite. Tool results sent back to the model omit the token.

Expected behavior  
The UI loads the pending row by conversation id. The model cannot supply a different payload at confirm time because the payload is the stored JSON.

Acceptance criteria  
- Confirm applies the staged payload, not a payload from the latest chat line.

Test cases  
- TC-SEC-03 `test_fr_tool_04_confirm_and_second_confirm`
- TC-SEC-03b expiry in `test_fr_data_01_quotes_and_expiry`

Error handling  
Expired rows move to `expired` and cannot be confirmed.

## FR-SEC-04 Secrets

Requirements  
Redact password, MFA code, and passcode assignments before storage and before the model call. Keep Azure credentials out of logs and repr.

Expected behavior  
"My password is Summer2026!" is stored as "My password is [redacted]". The reply tells the employee to change it and does not repeat the secret.

Acceptance criteria  
- `AzureConfig` repr hides the key.
- A missing `.env` raises `ConfigurationError` without echoing a key.

Test cases  
- TC-SEC-04 `test_fr_sec_04_secrets_and_config`
- TC-SEC-04b evaluation `SEC-SECRET`

Error handling  
Redaction failure is not silent: the substitution is deterministic.

## FR-SEC-05 Input length

Requirements  
Reject messages longer than 4000 characters before the model call.

Expected behavior  
The reply asks for a shorter problem statement. No ticket is created.

Acceptance criteria  
- 4001 characters is rule `length`. 4000 characters is not blocked for length.

Test cases  
- TC-SEC-05 `test_fr_sec_05_length`

Error handling  
Fixed refusal string.

---

## FR-EVAL-01 Reproducible cases

Requirements  
Ship a fixed offline suite for retrieval and agent policy.

Expected behavior  
`run_evaluation` rebuilds temporary databases and uses `ScriptedModel` or no model. Results do not depend on clock time except within a case's own latency measurement.

Acceptance criteria  
- The suite's pass rate is 1.0 on the approved fixtures.

Test cases  
- TC-EVAL-01 `test_fr_eval_01_suite_passes`

Error handling  
A failed case is listed by id. The suite does not raise unless the harness itself crashes.

## FR-EVAL-02 Latency

Requirements  
Record per-case wall-clock latency and the mean.

Expected behavior  
Each case result includes `latency_ms`. Offline cases finish in under 2 seconds each on the development machine.

Acceptance criteria  
- Mean and max are present and max is below 2000 ms in the automated test.

Test cases  
- TC-EVAL-02 `test_fr_eval_02_latency`

Error handling  
A timer wraps the case even when the case fails.

## FR-EVAL-03 Tool success

Requirements  
Report how many tool attempts returned `ok: true`.

Expected behavior  
Rejected and invalid tools count as attempts that did not succeed, so the rate can be below 1 while the suite still passes.

Acceptance criteria  
- `tools_total` is greater than `tools_ok` because `TOOL-UNKNOWN` and `TOOL-BAD-SERVICE` are included.
- The rate is present in the report.

Test cases  
- TC-EVAL-03 `test_fr_eval_03_tool_success`

Error handling  
Turns with no tools contribute zero to both counters.

## FR-EVAL-04 Answer quality signals

Requirements  
Report retrieval accuracy and, for agent turns that retrieved text, term coverage.

Expected behavior  
Retrieval accuracy is the fraction of labeled queries whose top document is the expected id. Coverage is the FR-RAG-03 score.

Acceptance criteria  
- Retrieval accuracy on the four labeled queries is 1.

Test cases  
- TC-EVAL-04 `test_fr_eval_04_retrieval_accuracy`

Error handling  
Coverage is null when the turn retrieved nothing.

## FR-EVAL-05 Dashboard

Requirements  
The Evaluation section runs the offline suite and shows pass count, mean latency, retrieval accuracy, tool success, and a per-case table.

Expected behavior  
The page does not call Azure. It explains that the model is scripted.

Acceptance criteria  
- The metrics match `run_evaluation` output.
- Failed ids, if any, are listed.

Test cases  
- TC-EVAL-05 manual UI check. The data contract is `test_fr_eval_01_suite_passes`.

Error handling  
Before the first run, the page tells the operator to run the suite.

## FR-EVAL-06 Mock model in automated tests

Requirements  
Pytest must not require Azure and must not open a network connection to call Claude.

Expected behavior  
Tests construct `ScriptedModel` or pass `model=None`.

Acceptance criteria  
- The suite passes with the three Azure variables unset.

Test cases  
- TC-EVAL-06 `test_fr_eval_01_suite_passes` executed without those variables.

Error handling  
Not applicable.

---

## FR-OPS-01 Environment configuration

Requirements  
Read `AZURE_ANTHROPIC_ENDPOINT`, `AZURE_ANTHROPIC_API_KEY`, and `AZURE_ANTHROPIC_MODEL` from the environment or `.env`.

Expected behavior  
Process variables win over `.env`. All three are required for a live client. Any missing name is reported.

Acceptance criteria  
- A temp `.env` with a fake key loads the model name.
- Repr does not include the key.

Test cases  
- TC-OPS-01 `test_fr_sec_04_secrets_and_config`

Error handling  
`ConfigurationError` names the missing variables and points at `.env.example`.

## FR-OPS-02 Do not commit secrets

Requirements  
`.env` is listed in `.gitignore`. `.env.example` contains empty or placeholder values only.

Expected behavior  
The example file documents the three names.

Acceptance criteria  
- `.gitignore` contains a `.env` line.
- The example file does not contain a real key.

Test cases  
- TC-OPS-02 `test_fr_ops_02_gitignore`

Error handling  
Not applicable.

## FR-OPS-03 Isolate the model client

Requirements  
The module that calls Azure does not import tickets, retrieval, or the agent.

Expected behavior  
Business rules stay in the agent, store, and security modules.

Acceptance criteria  
- `model_client.py` source does not reference `northstar_helpdesk.store`, `.rag`, or `.agent`.

Test cases  
- TC-OPS-03 `test_fr_ops_03_model_client_isolated`

Error handling  
SDK exceptions become `ModelError` inside the client.

## FR-OPS-04 Local except Claude

Requirements  
Documents, embeddings, tickets, traces, and the evaluation suite stay on disk. The only intended network client is `AnthropicFoundry`.

Expected behavior  
TF-IDF uses scikit-learn in process. SQLite uses a file under `data/`.

Acceptance criteria  
- No other HTTP client is constructed by application code.

Test cases  
- TC-OPS-04 code inspection in review. Automated proof is the absence of network calls in pytest.

Error handling  
Network failure on the Claude call is FR-AGENT-04.

## FR-OPS-05 Operator instructions

Requirements  
The README states how to create a virtual environment, install dependencies, set `.env`, run tests, and start Streamlit.

Acceptance criteria  
- `README.md` mentions `pytest` and `streamlit run app.py`.

Test cases  
- TC-OPS-05 `test_fr_ops_05_readme`

Error handling  
Not applicable.

## Out of scope

- Real VPN, email, or identity probes
- Multi-user authentication and authorization
- A vector database, LangChain, or a second agent
- Sending email or resetting passwords
- Natural-language confirmation of tickets
