# Architecture

Version: 1.0

## Summary

A single-process Streamlit application talks to one optional Azure Claude deployment. Documents, the TF-IDF index, tickets, and traces stay in the project directory.

```text
Employee
   │
   ▼
app.py  (Streamlit: Chat, Tickets, Evaluation)
   │
   ▼
runtime.HelpDesk
   │
   ├── agent.Agent ───────────── model_client.AnthropicAzureModel ──► Azure Claude
   │         │                         (or ScriptedModel / None)
   │         ├── security.screen_message / redact_secrets
   │         ├── rag.KnowledgeBase          (TF-IDF, knowledge/*.md)
   │         ├── services.ServiceCatalog    (data/services.json)
   │         └── store.Store                (data/helpdesk.db)
   │
   └── evaluation.run_evaluation  (temporary SQLite, scripted model)
```

## Modules

| Module | Responsibility |
| --- | --- |
| `app.py` | Pages, confirmation card, forms. No retrieval or SQL policy. |
| `northstar_helpdesk/runtime.py` | Builds the object graph. Swallows only `ConfigurationError` when Azure settings are absent. |
| `northstar_helpdesk/agent.py` | Loop, tool allowlist, citations, clarifier, fallback, trace wording. |
| `northstar_helpdesk/model_client.py` | `complete(system, messages, tools)` and error redaction. |
| `northstar_helpdesk/rag.py` | Chunk markdown on `##` headings, fit TF-IDF, cosine search. |
| `northstar_helpdesk/services.py` | Alias resolution and catalog reads. |
| `northstar_helpdesk/store.py` | SQLite, staged drafts, `confirm` / `cancel`. |
| `northstar_helpdesk/security.py` | Injection rules, secret redaction, length limit. |
| `northstar_helpdesk/config.py` | The three Azure variables. |
| `northstar_helpdesk/evaluation.py` | Offline cases and the report dictionary. |

The model client imports `config` and the Anthropic SDK only. It does not import `agent`, `store`, or `rag`.

## Request path

1. Redact secrets.
2. Screen the message. If blocked, store the turn and return. Do not call the model.
3. Load the last 12 plain messages. Append the new user message in memory and on disk.
4. If no model is configured, run the deterministic fallback and return.
5. Call the model with the four tool schemas.
6. If the response has no tool calls, finish.
7. Otherwise execute each call locally, append tool results, and repeat up to four rounds.
8. Finish: optional clarifier, citation block, confirmation notice, trace, assistant message.

Finish never calls `Store.confirm`.

## Tool boundary

| Tool | Effect |
| --- | --- |
| `search_knowledge_base` | Read-only search. |
| `check_service_status` | Read-only catalog lookup. |
| `create_support_ticket` | Insert `pending_actions` only. |
| `update_support_ticket` | Insert `pending_actions` only. |

`Store.confirm` is called from the Streamlit confirmation card and from tests. It is not a model tool. The token is stripped from the payload given back to the model; the card reloads the row by conversation id.

## Data

SQLite file `data/helpdesk.db`, created on startup.

- `conversations(id, requester, created_at)`
- `messages(id, conversation_id, role, content, trace_id, created_at)`
- `traces(id, conversation_id, events_json, created_at)`
- `tickets(id, conversation_id, title, description, category, priority, status, requester, created_at, updated_at)`
- `pending_actions(token, conversation_id, action, payload_json, created_at, expires_at, state)`

Ticket ids are `NS-` plus `1001 + count`. States for drafts are `pending`, `confirmed`, `cancelled`, and `expired`. Timestamps are UTC ISO-8601. The UI renders them in America/New_York.

The TF-IDF matrix is rebuilt in memory at process start from `knowledge/*.md`. It is not stored.

## External dependency

`AnthropicFoundry(api_key=..., base_url=endpoint, timeout=45, max_retries=1)` then `messages.create` with `max_tokens=900`. The model argument is the Azure deployment name from the environment.

No other module opens a network connection.

## Degradation

| Condition | Behavior |
| --- | --- |
| Azure variables missing | `model` is `None`. Fallback answers. Chat shows a sidebar warning. |
| SDK or timeout error | `ModelError`. Same fallback. No ticket write. |
| Unknown tool or bad arguments | Tool result `ok: false`. Loop continues. |
| Expired draft | `ConfirmationError`. No ticket write. |
| Empty retrieval | Reply says no document matched closely. |

## What is deliberately absent

- Vector database and embedding API
- LangChain or a multi-agent router
- Authentication
- A background worker
- Natural-language ticket confirmation

## Deployment shape

One virtual environment, one Streamlit process, one SQLite file. Suitable for a local demo, not for concurrent employees on a shared server. SQLite writes take a process lock so a single Streamlit rerun cannot interleave ticket confirms.
