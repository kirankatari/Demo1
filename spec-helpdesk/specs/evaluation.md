# Evaluation

Version: 1.0

## What is measured

The offline suite answers six questions:

1. Does TF-IDF put the labeled document first? (retrieval accuracy)
2. Does the loop execute the scripted tools and refuse the others? (agent policy)
3. Does a grounded VPN reply overlap the retrieved text? (term coverage)
4. Can a ticket appear without `confirm`? (must be no)
5. How long did each case take? (wall-clock milliseconds)
6. What share of tool attempts returned `ok: true`? (tool success)

It does not score a live Azure deployment. Live phrasing is checked by using the Chat page. An optional live run is out of the automated gate because the course environment may not have a key and because Claude output is not a stable oracle.

## Method

`run_evaluation(root)`:

- Builds one `KnowledgeBase` from `knowledge/`.
- Runs four retrieval cases against that index.
- For each agent case, creates a temporary SQLite file, a `ScriptedModel` or no model, and a new `Agent`.
- Times each case with `time.perf_counter`.
- Returns the summary below.

Pytest calls the same function and requires `pass_rate == 1`.

## Report

```text
passed, failed, case_count, pass_rate
mean_latency_ms, max_latency_ms, suite_latency_ms
tools_ok, tools_total, tool_success_rate
retrieval_accuracy
cases[]: id, kind, passed, latency_ms, tools_ok, tools_total, detail, coverage
```

The Evaluation page displays those fields. Tool success is expected to be below 100% because invalid and unknown tools are part of the suite. Those cases pass when the failure is contained.

Term coverage uses answer words longer than 3 characters, minus a small stop list, and ignores the `Sources:` block and the confirmation notice. A word counts as covered when it occurs in the retrieved excerpts or status JSON.

## Cases

| Id | Kind | Pass condition |
| --- | --- | --- |
| RET-VPN | retrieval | Top doc `vpn-remote-access` |
| RET-PASSWORD | retrieval | Top doc `password-mfa` |
| RET-TEAMS | retrieval | Top doc `email-and-teams` |
| RET-WIFI | retrieval | Top doc `office-wifi` |
| AGT-VPN | agent | Search and status, citation, "degraded", a question mark, coverage ≥ 0.25, no ticket, public trace |
| AGT-STAGE | agent | Pending create, zero ticket rows, reply says it has not created the ticket |
| AGT-CONFIRM | agent | After a separate `confirm` call, one `NS-` ticket at P1 and no open draft |
| AGT-UPDATE | agent | Priority unchanged after the tool, P1 only after `confirm` |
| SEC-INJECT | agent | Blocked, model `calls` empty, no ticket |
| SEC-SECRET | agent | `Summer2026` absent from storage and the reply |
| TOOL-UNKNOWN | agent | `tool_rejected`, no ticket |
| TOOL-BAD-SERVICE | agent | `tool_error`, model recovers, no ticket |
| AGT-LOOP | agent | `loop_limit`, no ticket |
| AGT-GREETING | agent | Four tools offered, none used |
| AGT-FALLBACK | agent | No model, VPN citation, degraded, clarifier, no ticket |
| AGT-MODEL-ERROR | agent | Timeout `ModelError` uses fallback, no ticket |
| CHAT-MEMORY | agent | Second request still contains the first user text |

## Quality bar for the reference answer

A passing VPN answer, model or fallback, must:

- Name the degraded status rather than invent an incident number
- Give the short path from the VPN document: Backup Gateway or a phone hotspot, and no reinstall in the next 30 minutes
- Cite `vpn-remote-access`
- Ask the operating system when it was not provided
- Leave the tickets table empty unless the operator uses the card

## Failure handling inside the suite

Case assertions set `passed` to false and still return a row. The harness itself may raise only on programmer errors (schema mistakes, missing corpus). Pytest then fails the build.

## Dashboard acceptance

After "Run offline evaluation":

- Passed equals case count
- Mean latency is shown in milliseconds
- Retrieval accuracy is 100%
- Tool success is shown as a percentage and is not required to be 100%
- Each case row shows result, latency, tool counts, coverage, and detail
