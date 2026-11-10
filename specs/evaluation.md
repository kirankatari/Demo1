# Evaluation

## 1. What is measured

The dashboard and `pytest` measure the application, not a live Claude score. Model wording in automated cases comes from a scripted mock. Retrieval, confirmation, injection, grounding, and latency are exercised through the real Python components.

| Metric | Definition | Source |
| --- | --- | --- |
| Case pass rate | Passed cases / all cases | Assertions in `eval/harness.py` |
| Latency | Wall-clock milliseconds of that case | `time.perf_counter` around the call |
| Tool success rate | Tool outcomes `success` / all tool outcomes in the run | Trace stages |
| Retrieval hit rate | Retrieval cases whose top passages include the expected document id / retrieval cases | TF-IDF results |
| Requirement coverage | Requirement ids attached to passing cases | `cases.json` |

Tool success is null when the run recorded no tool calls. The dashboard prints `n/a` for that state. The shipped suite does call tools, so a normal run has a numeric rate.

Live Claude quality is intentionally outside the automated score. A person can still type in the chat when `.env` is set. Those replies are not copied into the pass rate, because they are not reproducible.

## 2. Case file

`demo2_spec/northstar/eval/cases.json` is the case list. Each case has:

- `id`
- `requirement_ids`
- `kind`: `retrieval`, `fallback`, `security`, or `agent_mock`
- kind-specific inputs and expectations

The harness creates a temporary SQLite file per agent case so tickets cannot leak between cases.

## 3. Shipped cases

| Case id | Kind | What it locks |
| --- | --- | --- |
| `EVAL-RAG-VPN` | retrieval | Demo utterance retrieves `DOC-VPN-002` in the top 3 |
| `EVAL-RAG-PWD` | retrieval | Password reset retrieves `DOC-PWD-001` |
| `EVAL-RAG-EMPTY` | retrieval | Empty query returns no passages |
| `EVAL-FALLBACK-HERO` | fallback | Demo utterance searches, checks VPN, cites a real passage, asks a question, drafts an urgent ticket, writes nothing |
| `EVAL-FALLBACK-HELLO` | fallback | Greeting uses no tools |
| `EVAL-SEC-INJECT` | security | Override message does not call the mock model and writes no ticket |
| `EVAL-SEC-NORMAL` | security | Ordinary VPN request is not blocked |
| `EVAL-AGENT-SEARCH` | agent_mock | Scripted tool call then a cited answer; trace has no private-reasoning fields |
| `EVAL-AGENT-CONFIRM` | agent_mock | `propose_ticket` leaves the database empty and sets a pending proposal |
| `EVAL-AGENT-BOUND` | agent_mock | A tool call on every response stops at four model calls |
| `EVAL-AGENT-MEMORY` | agent_mock | Second turn sends the first user text to the mock |
| `EVAL-AGENT-TIMEOUT` | agent_mock | Timeout client falls back to local VPN content and writes no ticket |
| `EVAL-AGENT-FALSE-CLAIM` | agent_mock | "I've created the ticket" is corrected when nothing was committed |
| `EVAL-AGENT-BAD-CITE` | agent_mock | Unknown citation marker is removed |

## 4. Assertions that are not the dashboard

Pytest covers units the dashboard does not need to repeat in full: slug stability, settings redaction, Azure header and thinking-block parsing, invalid proposals, cancel, draft priority edit, and confirmed update. Those tests are part of acceptance. The dashboard is the reproducible end-to-end suite a reviewer can run from the UI.

## 5. How to run

```text
pytest
```

From the repository root, after installing `demo2_spec/requirements.txt`. No environment variables are required.

In the app, open Evaluation and choose Run evaluation. The page stores the JSON report in SQLite and renders the last run.

## 6. Pass rules for the hero fallback

`EVAL-FALLBACK-HERO` fails unless all of the following are true:

- trace contains successful `search_knowledge` and `check_service_status`
- VPN status used in the answer is degraded
- at least one citation marker is present and every marker was retrieved
- the answer contains a question mark
- the answer contains the action explanation
- pending proposal priority is `urgent`
- `SELECT COUNT(*) FROM tickets` is 0
- trace JSON does not contain the field names `thinking` or `chain_of_thought`

## 7. Latency

Latency includes local retrieval and SQLite. For mock cases it also includes the mock client's declared model latency only as part of the wall clock of the Python call, not as a separate invented number. The Azure parser records provider round-trip time on `model_call` stages when the live client is used. The dashboard suite does not use the live client, so its latency is the local stack.

## 8. Failure display

A failed case stores `passed: false` and a human-readable `note` naming the first broken assertion. Later assertions for that case still run so the note can list every miss. One failure does not stop the suite.

## 9. What this evaluation will not claim

- It does not claim the live model always chooses the right tool.
- It does not use an LLM-as-judge.
- It does not measure employee satisfaction.
- A passing citation check means the id was retrieved, not that the procedure is the best possible IT advice.
