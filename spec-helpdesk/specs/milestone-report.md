# Milestone report

Date of the acceptance run: November 10, 2026.

The modules were written to match milestones M1 through M7 in `implementation-plan.md`. The gate below is one `pytest` run from `spec-helpdesk` (M8), not seven separate historical runs. No requirement text was edited to turn a failure into a pass.

Command:

```bash
cd spec-helpdesk
pytest -q
```

Result: **23 passed, 0 failed**, about 1.0 second. Azure variables were unset. No network call.

The vibe-coded twin was checked separately: `vibe-helpdesk` **18 passed, 0 failed**, about 1.1 seconds.

## Requirements by milestone

| Milestone | Requirements | Tests in the M8 run | Result |
| --- | --- | --- | --- |
| M1 Skeleton and storage | FR-OPS-01, FR-OPS-02, FR-DATA-01, FR-SEC-03, FR-SEC-04 config/repr | `test_fr_sec_04_secrets_and_config`, `test_fr_ops_02_gitignore`, `test_fr_data_01_quotes_and_expiry`, `test_fr_tool_04_confirm_and_second_confirm` | Passed |
| M2 Corpus and retrieval | FR-RAG-01, FR-RAG-02 | `test_fr_rag_01_corpus_files`, `test_fr_rag_02_labeled_queries` | Passed |
| M3 Security screen | FR-SEC-01, FR-SEC-04 redaction, FR-SEC-05 | `test_fr_sec_01_injection`, secret assertion inside `test_fr_sec_04_secrets_and_config`, `test_fr_sec_05_length` | Passed |
| M4 Catalog and drafts | FR-DATA-02, FR-TOOL-01, FR-TOOL-02, FR-TOOL-03 | `test_fr_tool_01_catalog`, `test_fr_tool_02_stage_only`, suite `AGT-UPDATE` via `test_fr_eval_01_suite_passes` | Passed |
| M5 Agent | FR-AGENT-01–04, FR-CHAT-02–04, FR-RAG-04, FR-TOOL-05, FR-SEC-02, FR-OPS-03, FR-OPS-04 | `test_fr_chat_02_conversation_memory`, `test_fr_chat_03_trace_is_public`, `test_fr_chat_04_windows_skips_forced_question`, `test_fr_agent_02_loop_bound`, `test_fr_sec_02_user_json_does_not_create_ticket`, `test_fr_ops_03_model_client_isolated` | Passed |
| M6 Evaluation | FR-EVAL-01–04, FR-EVAL-06, FR-RAG-03 | `test_fr_rag_03_grounding_score`, `test_fr_eval_01_suite_passes`, `test_fr_eval_02_latency`, `test_fr_eval_03_tool_success`, `test_fr_eval_04_retrieval_accuracy` | Passed |
| M7 Streamlit | FR-CHAT-01, FR-EVAL-05, FR-OPS-05 | `test_fr_ops_05_readme`. Chat, Tickets, and Evaluation exercised in the browser after this run. | README passed. Browser notes are in the PR summary. |
| M8 Regression | All of the above | 23 tests | 23 passed, 0 failed |

The offline suite inside that run also passed every case in `evaluation.md`, including retrieval accuracy 1.0 and a tool-success rate below 1.0 because unknown and invalid tools are deliberate cases.

## Clarification after the first UI pass

The VPN fallback also cited `password-mfa` because one chunk scored 0.088, just over the 0.08 floor, beside a 0.425 VPN hit. `FR-RAG-02` now also drops hits below 25% of the best score. That still satisfies the 0.08 minimum. Both apps were retested after the change.

## Deviations

None. The implementation follows the approved specs:

- Four tools, four-round cap, confirm is not a tool
- TF-IDF threshold 0.08, citations appended by code
- 30-minute draft expiry
- Scripted evaluation, no live Claude oracle

## Outstanding risks

- The injection list is lexical. A novel jailbreak can reach the model. It still cannot write a ticket without the confirmation card.
- Live tool choice depends on the Azure deployment and is not what the offline suite measures.
- "you are now" can match a harmless sentence. The reference VPN request does not.
- SQLite is unencrypted and the app is single-operator.
- The operator must supply the three Azure variables before live phrasing can be tried. Until then the fallback path is the demo.
