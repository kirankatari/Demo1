# Specification review

Version: 1.0, reviewed before implementation.  
No application code is authorized by this review except the later explicit implementation request, which approved the `specs/` documents as written.

## Completeness

The six feature groups in the assignment are covered:

| Assignment ask | Where it lives |
| --- | --- |
| Chat | FR-CHAT-01, FR-CHAT-02 |
| RAG with local TF-IDF | FR-RAG-01 through FR-RAG-04 |
| Agent chooses direct answer, retrieval, or tools | FR-AGENT-01, agent-design.md |
| Service status and tickets | FR-TOOL-01 through FR-TOOL-05 |
| Memory | FR-CHAT-02 |
| Trace without private reasoning | FR-AGENT-03, FR-CHAT-03 |
| Injection protection and ticket confirmation | security.md |
| Evaluation dashboard, latency, tool success | FR-EVAL-01 through FR-EVAL-05 |
| SQLite and fictional documents | FR-DATA-01, FR-DATA-02 |
| Azure settings in `.env`, nothing else remote | FR-OPS-01 through FR-OPS-04 |

Missing items that were added during this review, because the original paragraph did not decide them:

- Draft expiry (30 minutes) and a single open draft per conversation
- Secret redaction separate from injection blocking
- A 4000-character cap
- Ticket modification, not only creation, behind the same confirm path
- A no-model fallback so the demo runs without a key
- Citation text produced by code, not hoped for from the model
- An explicit statement that "yes" in chat is not confirmation

## Contradictions that were resolved

1. "The agent can create tickets" versus "never create a ticket without confirmation."  
   Resolution: the tool stages. `Store.confirm` writes. The model has no confirm tool.

2. "Retrieve documents" could mean always-on RAG or a chosen tool.  
   Resolution: retrieval is a tool the model may skip. The fallback retrieves only when the model is absent or failing. Greetings are not forced through search.

3. "Evaluate answer quality" could be read as a live Claude score.  
   Resolution: automated quality is retrieval rank plus term coverage against retrieved text. Live quality is a manual chat check. The dashboard says the suite is scripted.

4. "Explain reasoning" versus "do not expose private model reasoning."  
   Resolution: the trace explains application stages in fixed sentences. Model prose is not a trace field.

## Agentic versus deterministic

| Operation | Owner | Why |
| --- | --- | --- |
| Phrase the reply and choose a tool | Model | Several valid next steps; wording matters |
| Injection screen, redaction, length | Deterministic | Must be stable under attack strings |
| TF-IDF rank | Deterministic | The corpus is the oracle |
| Catalog read | Deterministic | Status is a fixture |
| Argument checks, allowlist | Deterministic | The model must not widen its own tools |
| Ticket insert and update | Deterministic, and only after the card | Authorization is not a language task |
| Citations and the OS clarifier | Deterministic post-step | Grounding should not depend on the model remembering a format |
| Fallback answer | Deterministic | Used exactly when the model cannot be trusted to run |
| Evaluation oracles | Deterministic scripts | Otherwise the gate flakes |

## RAG grounding and citations

- Hits below 0.08 are dropped so a weak neighbor is not cited.
- The reply's `Sources:` block is built from the hits actually returned, not from a model-written bibliography.
- Term coverage compares the answer body with those excerpts. The VPN case fails if coverage is under 0.25.
- The fallback copies excerpt text into the reply so an operator without a key still sees the document, not a invented procedure.
- Documents are tool results, not system-prompt text, so a sentence in a file cannot rewrite the tool rules.

## Unauthorized tool execution

- Allowlist of four names.
- Schema check plus Python validators.
- User text is not a tool channel (FR-SEC-02).
- `confirm` is unreachable from the model.
- The token is not in the tool result.
- Confirm reloads payload from SQLite.

## Ticket confirmation

The card is the only writer. Cancel and expiry are specified. A second confirm fails. Chat agreement does nothing to the tickets table.

## Measurement

See `evaluation.md`. Pass rate, mean and max latency, retrieval accuracy, and tool success are all fields on the report. Tool success is intentionally not 100% because bad tool calls are cases. The suite passes when those failures are contained.

## API and tool failures

| Failure | Response |
| --- | --- |
| Missing `.env` | Fallback, sidebar warning, no exception shown to the employee as a stack trace |
| Timeout or SDK error | `ModelError` with redacted, truncated text, then fallback |
| Unknown tool | `tool_rejected`, then the model may answer |
| Bad arguments or unknown service | `tool_error`, then the model may answer |
| Four tool rounds | Stop, one tool-free final call, else summarize collected results |
| Expired or reused token | `ConfirmationError`, no write |
| SQLite error on confirm | `StorageError`, transaction rolled back |

## Complexity that was rejected

- Vector database: eight short documents do not need one, and the assignment forbids requiring one.
- LangChain / extra agent framework: the loop is a few dozen lines and is easier to test directly.
- Login and roles: no identity provider was requested.
- A second "planner" model call: it would double latency and give the tests nothing stable to assert.
- Parsing "yes" as confirmation: it makes injection easier.

## Unresolved decisions

None that block implementation.

The operator still has to supply the real Azure endpoint, key, and deployment name. Those are configuration, not product decisions. Until they exist, FR-AGENT-04 defines the behavior.

The lexical injection list will miss new jailbreaks. That residual risk is accepted in `security.md` because the confirmation gate does not depend on the classifier.

## Approval state

These `specs/` documents are the implementation baseline: `requirements.md`, `architecture.md`, `agent-design.md`, `security.md`, `evaluation.md`, and `implementation-plan.md`. The traceability matrix points each requirement at a test. Implementation must follow the milestones and must not treat this review as permission to add services, tools, or a vector store.
