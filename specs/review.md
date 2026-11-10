# Specification review

Review of `requirements.md`, `architecture.md`, `agent-design.md`, `security.md`, `evaluation.md`, and `implementation-plan.md` before implementation.

## 1. Completeness

The six documents name the same product, the same four tools, the same confirmation rule, and the same evaluation cases. Every functional requirement in the inventory has expected behavior, acceptance criteria, a test, and an error path. Non-functional items `NFR-01` through `NFR-05` are covered by the plan's environment and by the validation limits in the tool and ticket sections.

The UI requirements are specific enough to implement: chat, sample utterance, trace, tickets list, staged edit, evaluation page. Visual styling is not a requirement. The implementation may style the page as an internal help desk as long as the behaviors above stay intact.

## 2. Contradictions

None remain after the decisions in section 6.

Checked pairs:

- "The agent decides whether to retrieve" and "retrieval is deterministic TF-IDF". These fit. The model (or the fallback router) decides whether to call `search_knowledge`. The ranking itself is deterministic.
- "Conversation memory" and "no conversation table". Memory is in the session object, which is what FR-CHAT-02's error path describes.
- "Never say a ticket was created" and "confirmation creates a ticket". The claim guard looks at whether `commit_pending` ran on that turn.
- "Local except the Claude API" and "evaluation dashboard". The dashboard runs mocks and local code only.

## 3. Missing dependencies

Implementation needs Python 3.12, Streamlit, scikit-learn, httpx, python-dotenv, and pytest. All are declared in the plan and pinned when the environment is created. SQLite is in the Python standard library. No vector database, Redis, or server process is required.

Azure is an optional runtime dependency. The spec says how the app behaves when it is absent, so a missing key is not a missing build dependency.

## 4. Complexity that was removed

- No vector store and no embedding call. TF-IDF is enough for this corpus and is what the brief requires.
- No tool that commits a ticket. A commit tool would duplicate the confirmation gate and give the model a way to press it.
- No second model call to judge answers. The eval assertions are deterministic.
- No persisted chat transcript. Session memory meets the requirement with less schema.
- No authentication system. The actor is one local employee with a display name.

Agentic choice is limited to routing and phrasing. Search math, status lookup, validation, and SQL remain ordinary code.

## 5. Grounding and citations

The fallback copies sentences from retrieved passages and marks those passage ids. The loop then checks that every marker was retrieved on that turn and strips the others. Status text is labeled separately so a gateway incident is not disguised as a policy citation. This verifies citation support. It does not verify that the quoted sentence is the best troubleshooting step; that limit is stated in `evaluation.md`.

## 6. Decisions closed so implementation can start

| Question | Decision |
| --- | --- |
| Which Azure shape? | Anthropic Messages URL in `AZURE_CLAUDE_ENDPOINT`, auth style configurable. |
| Is employee login required? | No. Sidebar display name only. |
| Can the demo run without a key? | Yes. Local fallback uses the same tools and the same confirmation gate, and the reply says the model was not used. |
| Are ticket edits in scope? | Yes. `propose_ticket_update` and the tickets page both stage a change and wait for confirmation. |
| How does the employee confirm? | Confirm button, or a chat message that is only an exact confirmation phrase. |
| Where does memory live? | Browser session, last 20 turns sent to the model. |

No blocking questions remain. If a later test shows one of these decisions is wrong, update this file and the affected requirement before changing the code.

## 7. Unauthorized tool execution

The registry rejects unknown names and non-object arguments. The model never receives a commit function. `propose_*` writes only an in-memory proposal and returns `committed=false`. `commit_pending` checks that a proposal is still current. SQL update columns are a fixed set.

## 8. Ticket confirmation

Create and update share `TicketProposal`. The database changes only inside `commit_pending` after a button press or an exact phrase. Injection screening runs first, so a confirm phrase wrapped in an override is refused. A longer "yes, …" sentence is not an exact phrase. Cancel and "change priority to …" do not write.

## 9. Measurement

`evaluation.md` defines pass rate, wall-clock latency, tool success, and retrieval hit rate. The case file is shared by pytest and the dashboard. Live Claude calls are excluded from the score so the result is reproducible on a machine with no credential.

## 10. API and tool failures

`FR-OPS-01` is the failure table. Timeouts and server errors fall back to local tools. Authentication and not-found errors say what to check and still offer the local answer. Tool errors become tool results or, on the fallback path, a sentence in the reply. They do not commit a proposal.

## 11. Requirements-to-tests traceability

| Requirement | Component | Tests |
| --- | --- | --- |
| FR-CHAT-01 | `streamlit_app.py` | `test_app_renders_chat`, `test_hero_fallback_end_to_end` |
| FR-CHAT-02 | `agent/loop.py` | `test_memory_includes_prior_turn`, `EVAL-AGENT-MEMORY` |
| FR-CHAT-03 | `agent/fallback.py` | `test_hero_fallback_end_to_end`, `EVAL-FALLBACK-HERO` |
| FR-CHAT-04 | `agent/loop.py` | `test_hero_fallback_end_to_end` |
| FR-RAG-01 | `knowledge/` | `test_corpus_contains_required_documents` |
| FR-RAG-02 | `rag/retriever.py` | `test_hero_query_retrieves_vpn_troubleshooting`, `test_password_query_retrieves_password_doc`, `EVAL-RAG-VPN`, `EVAL-RAG-PWD`, `EVAL-RAG-EMPTY` |
| FR-RAG-03 | `agent/grounding.py`, `agent/fallback.py` | `test_fallback_citations_are_grounded`, `test_unsupported_citation_is_stripped`, `EVAL-AGENT-BAD-CITE` |
| FR-AGENT-01 | `agent/loop.py`, `agent/fallback.py` | `test_greeting_skips_tools`, `test_mock_agent_searches_then_answers`, `EVAL-FALLBACK-HELLO`, `EVAL-AGENT-SEARCH` |
| FR-AGENT-02 | `agent/loop.py` | `test_loop_stops_at_max_steps`, `EVAL-AGENT-BOUND` |
| FR-AGENT-03 | `agent/loop.py`, `llm/client.py` | `test_trace_has_no_private_reasoning`, `test_azure_client_strips_thinking` |
| FR-TOOL-01 | `tools/registry.py`, `data/service_status.json` | `test_vpn_status_degraded`, `test_unknown_service_is_error` |
| FR-TOOL-02 | `tools/registry.py` | `test_propose_does_not_insert_ticket`, `test_invalid_proposal_rejected` |
| FR-TOOL-03 | `security/confirmation.py`, `agent/loop.py`, `db.py` | `test_exact_yes_commits_ticket`, `test_yes_with_extra_text_does_not_commit`, `test_cancel_does_not_insert`, `test_priority_edit_updates_draft_only`, `test_update_requires_confirmation`, `EVAL-AGENT-CONFIRM` |
| FR-SEC-01 | `security/injection.py` | `test_injection_blocks_override`, `test_injection_allows_normal_vpn_request`, `test_injection_allows_confirmation_in_normal_sentence`, `test_indirect_injection_passage_is_neutralized`, `EVAL-SEC-INJECT`, `EVAL-SEC-NORMAL` |
| FR-SEC-02 | `tools/registry.py` | `test_unknown_tool_rejected` |
| FR-SEC-03 | `config.py`, `models.py` | `test_settings_redact_key`, `test_trace_redacts_secret_like_strings` |
| FR-DATA-01 | `db.py` | `test_exact_yes_commits_ticket` |
| FR-DATA-02 | `llm/client.py`, `agent/fallback.py` | `test_hero_fallback_end_to_end`, `test_azure_client_strips_thinking` |
| FR-EVAL-01 | `eval/harness.py`, evaluation page | `test_eval_harness_passes` |
| FR-EVAL-02 | `eval/harness.py` | `test_eval_harness_passes` |
| FR-EVAL-03 | `llm/client.py`, `tests/` | full `pytest` with `MockLLMClient` |
| FR-OPS-01 | `agent/loop.py` | `test_api_timeout_uses_local_documents`, `EVAL-AGENT-TIMEOUT` |
| FR-UX-01 | `streamlit_app.py`, `db.py` | `test_update_requires_confirmation` |
| NFR-01 | `requirements.txt` | environment install |
| NFR-02 | `eval/harness.py` | `pytest` with no `.env` |
| NFR-03 | `.gitignore`, `.env.example` | review of the tree; no key in source |
| NFR-04 | `agent/loop.py`, `tools/registry.py` | `test_loop_stops_at_max_steps` |
| NFR-05 | `tools/registry.py` | `test_invalid_proposal_rejected` |

## 12. Outstanding risks

- Lexical injection filters miss paraphrases. The write gate is the backstop.
- Live model tool choice can differ from the fallback. The score does not hide that; it simply does not pretend a live call is a unit test.
- Session memory disappears when the browser session ends. Tickets remain.
- TF-IDF can rank the wrong passage if the corpus grows without adding tests. The two retrieval cases are the regression check for the current corpus.
