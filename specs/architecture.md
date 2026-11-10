# Architecture: Northstar IT Help Desk

Specification for `demo2_spec/`. The running system is a single-process Streamlit application. SQLite, documents, and TF-IDF stay on the machine. Azure is called only by `northstar.llm.client.AzureClaudeClient`.

## 1. Context

```text
Employee browser
    |
    v
Streamlit UI  (chat, tickets, evaluation)
    |
    v
HelpDeskAgent  ---- optional HTTP ---->  Azure Claude Messages API
    |
    +-- Injection screen and confirmation gate   (deterministic)
    +-- KnowledgeBase TF-IDF                     (deterministic)
    +-- ServiceStatus JSON                      (deterministic)
    +-- Ticket database SQLite                   (deterministic)
    +-- Fallback responder                       (deterministic, used when no model is available)
```

## 2. Repository layout

```text
demo2_spec/
  streamlit_app.py           UI only. No retrieval or SQL logic.
  requirements.txt
  knowledge/                 Fictional IT documents.
  data/service_status.json   Simulated status catalog.
  northstar/
    config.py                Environment loading and redacted settings.
    models.py                Dataclasses and allowed enumerations.
    db.py                    SQLite tickets and eval-run storage.
    runtime.py               Wires the objects the UI and tests use.
    rag/retriever.py         Chunking and TF-IDF.
    security/injection.py    Request and passage screening.
    security/confirmation.py Exact confirm and cancel phrases.
    tools/registry.py        Allowlisted tools.
    llm/client.py            Azure client, response parser, mock client.
    agent/prompts.py         System prompt.
    agent/grounding.py       Citation checks.
    agent/fallback.py        Local responder.
    agent/loop.py            Bounded agent loop.
    eval/cases.json          Reproducible cases.
    eval/harness.py          Runner used by pytest and the dashboard.
  tests/                     Unit and integration tests. No live API.
```

## 3. Module responsibilities

| Module | Responsibility | Depends on |
| --- | --- | --- |
| `streamlit_app.py` | Session state, layout, buttons that confirm tickets | `runtime`, agent, database |
| `config.py` | Read env, default local paths, redact secrets | `python-dotenv` |
| `rag/retriever.py` | Load markdown, chunk on headings, fit TF-IDF, search | `scikit-learn` |
| `security/*` | Decide what may reach the model or the database | none |
| `tools/registry.py` | Validate arguments and run one allowlisted action | retriever, status, proposals |
| `llm/client.py` | HTTP and parsing, or a scripted mock | `httpx` |
| `agent/loop.py` | Order the screen, memory, model, tools, grounding, and claims guard | all of the above |
| `agent/fallback.py` | Same tools without a model | tools, grounding |
| `db.py` | Persist tickets only after a confirmed proposal | SQLite |
| `eval/harness.py` | Execute cases and aggregate metrics | agent, retriever |

The model client does not import the database or the retriever. Business rules do not build HTTP requests.

## 4. Runtime objects

`build_runtime(settings, llm=None)` constructs a knowledge base, a status catalog, a database, a tool registry, and a `HelpDeskAgent`.

When `llm` is omitted and endpoint, key, and model are all set, the runtime builds `AzureClaudeClient`. Otherwise the agent runs in local mode and says so on each IT answer.

Tests pass a `MockLLMClient` or a client that raises. They pass a temporary database path.

## 5. Data

### 5.1 Documents

Markdown files with a `Document-ID:` line and `##` sections. A section becomes a passage id `{document_id}#{heading-slug}`. The indexed text is the title, the heading, and the body.

### 5.2 Service status

`data/service_status.json` is the only status source. The sidebar reads it for display. The agent reads it through `check_service_status`, so the trace shows the check.

### 5.3 SQLite

File default: `demo2_spec/data/helpdesk.db` (gitignored).

`tickets`: id, requester, category, priority, service, summary, description, status, created_at, updated_at.

`ticket_events`: ticket id, event name, detail, created_at. Confirmation writes `confirmed_create` or `confirmed_update`.

`eval_runs`: id, created_at, JSON report.

Conversations are not stored in SQLite. They live in `st.session_state` for the browser session. This matches FR-CHAT-02 and keeps the agent testable without Streamlit.

### 5.4 Ticket lifecycle

```text
propose_ticket / propose_ticket_update
    -> validated TicketProposal on the conversation
    -> UI shows Confirm and Cancel
    -> commit_pending writes SQL
    -> pending cleared only after the write succeeds
```

Nothing in `llm/client.py` can skip this path. The tool result text tells the model the proposal was not submitted.

## 6. Request path

1. Screen the user text. On a block, refuse and stop.
2. If a proposal is pending and the text is an exact confirmation or cancellation, commit or drop it and stop.
3. If a proposal is pending and the text only changes its priority, update the draft and stop.
4. Append the user turn to session memory.
5. If no model client is configured, run the fallback responder and stop.
6. Otherwise call the model with the system prompt, the last 20 turns, and the four tool schemas.
7. On a tool-use stop, execute each call, append tool results, and repeat up to four model calls.
8. On a final text stop, run the citation check and the false-creation guard.
9. Append the action summary from the trace.
10. Return the answer, citations, pending proposal, and trace to the UI.

Timeouts and 5xx responses leave the model path and enter step 5, with a sentence that names the failure.

## 7. Deployment and configuration

Local process:

```text
streamlit run demo2_spec/streamlit_app.py
```

Environment variables:

| Variable | Required for live model | Purpose |
| --- | --- | --- |
| `AZURE_CLAUDE_ENDPOINT` | yes | Full Messages URL |
| `AZURE_CLAUDE_API_KEY` | yes | Secret |
| `AZURE_CLAUDE_MODEL` | yes | Model or deployment name |
| `AZURE_CLAUDE_API_VERSION` | no | Default `2023-06-01` |
| `AZURE_CLAUDE_AUTH_STYLE` | no | `api-key`, `x-api-key`, or `bearer` |

The app loads the first `.env` found in the current directory, `demo2_spec/`, or the repository root. It does not override variables already set in the process.

## 8. Why this shape

Streamlit is the required UI and is enough for one local user. SQLite is the required ticket store and needs no separate server. TF-IDF fits the corpus in memory and avoids a vector database. The agent boundary is small on purpose: the model chooses and phrases; Python decides what is allowed to run and what is allowed to be stored.
