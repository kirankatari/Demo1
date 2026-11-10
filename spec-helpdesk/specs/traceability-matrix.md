# Requirements to tests

The automated tests live in `spec-helpdesk/tests/test_requirements.py` unless a row says the check is inside the offline suite. Suite case ids are defined in `evaluation.md` and executed by `run_evaluation`.

| Requirement | Test |
| --- | --- |
| FR-CHAT-01 | Manual chat bubble. Data path covered by FR-CHAT-02 persistence. |
| FR-CHAT-02 | `test_fr_chat_02_conversation_memory`; suite `CHAT-MEMORY` |
| FR-CHAT-03 | `test_fr_chat_03_trace_is_public`; suite `AGT-VPN` |
| FR-CHAT-04 | Suite `AGT-VPN`, `AGT-FALLBACK`; `test_fr_chat_04_windows_skips_forced_question` |
| FR-RAG-01 | `test_fr_rag_01_corpus_files` |
| FR-RAG-02 | `test_fr_rag_02_labeled_queries`; suite `RET-VPN`, `RET-PASSWORD`, `RET-TEAMS`, `RET-WIFI` |
| FR-RAG-03 | `test_fr_rag_03_grounding_score`; suite `AGT-VPN` coverage gate |
| FR-RAG-04 | Suite `AGT-VPN`, `AGT-FALLBACK` citation assertion |
| FR-AGENT-01 | Suite `AGT-GREETING`, `AGT-VPN` |
| FR-AGENT-02 | `test_fr_agent_02_loop_bound`; suite `AGT-LOOP` |
| FR-AGENT-03 | `test_fr_chat_03_trace_is_public` |
| FR-AGENT-04 | Suite `AGT-FALLBACK`, `AGT-MODEL-ERROR` |
| FR-TOOL-01 | `test_fr_tool_01_catalog`; suite `TOOL-BAD-SERVICE` |
| FR-TOOL-02 | `test_fr_tool_02_stage_only`; suite `AGT-STAGE` |
| FR-TOOL-03 | Suite `AGT-UPDATE` |
| FR-TOOL-04 | `test_fr_tool_04_confirm_and_second_confirm`; suite `AGT-CONFIRM` |
| FR-TOOL-05 | Suite `TOOL-UNKNOWN`, `TOOL-BAD-SERVICE` |
| FR-DATA-01 | `test_fr_data_01_quotes_and_expiry` |
| FR-DATA-02 | `test_fr_tool_01_catalog` |
| FR-SEC-01 | `test_fr_sec_01_injection`; suite `SEC-INJECT` |
| FR-SEC-02 | `test_fr_sec_02_user_json_does_not_create_ticket` |
| FR-SEC-03 | `test_fr_tool_04_confirm_and_second_confirm`; expiry in `test_fr_data_01_quotes_and_expiry` |
| FR-SEC-04 | `test_fr_sec_04_secrets_and_config`; suite `SEC-SECRET` |
| FR-SEC-05 | `test_fr_sec_05_length` |
| FR-EVAL-01 | `test_fr_eval_01_suite_passes` |
| FR-EVAL-02 | `test_fr_eval_02_latency` |
| FR-EVAL-03 | `test_fr_eval_03_tool_success` |
| FR-EVAL-04 | `test_fr_eval_04_retrieval_accuracy` |
| FR-EVAL-05 | Manual Evaluation page. Report contract covered by FR-EVAL-01. |
| FR-EVAL-06 | `test_fr_eval_01_suite_passes` with Azure variables unset |
| FR-OPS-01 | `test_fr_sec_04_secrets_and_config` |
| FR-OPS-02 | `test_fr_ops_02_gitignore` |
| FR-OPS-03 | `test_fr_ops_03_model_client_isolated` |
| FR-OPS-04 | No HTTP client outside `model_client.py`; pytest does not call Azure |
| FR-OPS-05 | `test_fr_ops_05_readme` |

Manual rows are the Streamlit surfaces. They are checked in the browser after M7. They are not given a fake automated pass.
