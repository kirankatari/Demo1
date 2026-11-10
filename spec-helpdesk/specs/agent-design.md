# Agent design

Version: 1.0

## When the model is needed

The model is needed to choose among a direct answer, document search, a service check, and a ticket draft, and to phrase the reply.

The model is not needed for:

- injection screening and secret redaction
- TF-IDF ranking
- catalog lookup once a service id is known
- argument validation
- writing a ticket (forbidden for the model)
- citation formatting
- the operating-system clarifier when the model forgot the question mark
- the offline evaluation harness

Those steps are ordinary Python. Putting them behind another model call would make the safety tests non-reproducible.

## Loop

```text
screen(message)
if blocked: return refusal
if model is None: return fallback(search, status)
repeat up to 4 times:
    response = model(tools=ALLOWLIST)
    if response has no tool call: return finish(response.text)
    execute allowlisted calls
    append tool results
record loop_limit
final = model(tools disabled)
return finish(final text or a summary of tool results)
```

`MAX_TOOL_ROUNDS` is 4. `MEMORY_MESSAGES` is 12.

## System prompt contract

The prompt tells the model the employee display name and the four choices. It forbids claiming a ticket was created, forbids invented incident numbers, and tells it to ignore instructions inside the user message that conflict with those rules.

The prompt is not copied into the trace.

## Tools

### search_knowledge_base

Input: `query` string, at least 2 non-space characters.  
Output: up to 4 hits with `doc_id`, `title`, `heading`, `excerpt`, `score`. Hits under 0.08, and hits under 25% of the best score, are omitted.  
Failure: validation error, or an empty list when nothing remains.

### check_service_status

Input: `service_id` string. Aliases such as "Northstar Connect" map to `vpn`.  
Output: `ok`, `service_id`, `name`, `status`, `summary`, `workaround`.  
Failure: `{ok: false, error}` for unknown ids. This is a successful recovery, not an exception.

### create_support_ticket

Input: `title`, `description`, `category` (`network`, `access`, `email`, `hardware`, `security`, `other`), `priority` (`P1`–`P4`), optional `requester`.  
Output: `{ok: true, status: "pending_confirmation", draft}` without the confirmation token.  
Side effect: one pending row. Any older pending row for the conversation is cancelled.  
The model is instructed not to say the ticket exists. The application also appends: "I have not created or changed a ticket."

### update_support_ticket

Input: `ticket_id` (`NS-` plus digits) and `status` and/or `priority`.  
Output: pending confirmation, no token.  
Side effect: pending row only. The ticket row is unchanged until the card is confirmed.  
Notice text: "I have not modified the ticket."

## Fallback

Used when the client is missing or `complete` raises `ModelError`.

1. Search with the raw employee message.
2. If the message names a catalog alias, check that service. Longer aliases win over overlapping shorter ones. Results are ordered by position in the message.
3. Reply with the status sentences, up to two excerpts, and the sentence "I have not created a ticket."
4. Apply the same clarifier and citation rules as a model answer.

The fallback has no create or update tool.

## Clarifier

If the lowercased message contains `vpn` and one of `disconnect`, `dropping`, or `drops`, and it does not name an operating system, and the draft reply has no `?`, append:

"Which operating system is Northstar Connect running on?"

## Citations

After the clarifier, append:

```text
Sources:
- Northstar Connect VPN (vpn-remote-access)
```

One line per distinct `doc_id`, in retrieval order.

## Trace

Each event:

```json
{
  "stage": "tool_call",
  "summary": "Searched internal IT documents.",
  "because": "Troubleshooting and policy stay tied to Northstar documents.",
  "detail": {"tool": "search_knowledge_base", "result_count": 2, "documents": ["vpn-remote-access"], "ok": true}
}
```

Allowed detail keys: `blocked`, `rule`, `tool`, `query`, `result_count`, `documents`, `service_id`, `ok`, `error`, `latency_ms`, `stop_reason`, `tool_count`, `action`, `redacted`, `round`, `status`.

`model_response` records metadata only. The because line says model prose is not stored.

Strings that look like API keys are replaced with `[redacted]` before the event is stored.

## Reference scenario

Employee: VPN disconnecting, working remotely, client presentation in 30 minutes.

A competent model turn:

1. `search_knowledge_base` for the disconnect and the presentation.
2. `check_service_status` for `vpn` (catalog says degraded; workaround is Backup Gateway or a phone hotspot; do not reinstall in the next 30 minutes).
3. Answer from those results, cite `vpn-remote-access`, and ask the operating system if it is still unknown.
4. Stage a P1 network ticket only if the employee asked for one or the documents' escalate section applies and the model chooses to offer it. Even then the ticket row does not exist until the card is confirmed.

The offline VPN case scripts steps 1 and 2 and a grounded sentence, then asserts the clarifier, the citation, degraded status, and zero tickets. That case checks the loop. It does not claim the live model will pick the same tools. Live tool choice is manual.

## Memory

Only `user` and `assistant` plain text are reloaded. In-turn tool blocks stay in the local message list and die with the turn. This keeps the next turn valid for the Claude API without replaying raw tool ids.
