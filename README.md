# Vibe coding vs spec-driven coding

Two local IT help desks for the fictional company Northstar Technologies. Both answer the same employee:

> My VPN keeps disconnecting. I am working remotely, and I have a client presentation in 30 minutes. Can you help?

| | Vibe-coded | Spec-driven |
| --- | --- | --- |
| Path | `vibe-helpdesk/` | `spec-helpdesk/` |
| Order | Working code, then notes | `specs/` first, then code that cites requirement ids |
| Decisions | `vibe-helpdesk/NOTES.md` (written after the code) | `spec-helpdesk/specs/review.md` (written before the spec implementation) |
| Tests | `vibe-helpdesk/tests/test_helpdesk.py` | `spec-helpdesk/tests/test_requirements.py` plus the traceability matrix |

Shared behavior, because both assignment briefs asked for it:

- Streamlit chat with conversation memory
- TF-IDF search over fictional IT documents, no vector database
- An agent that may answer, search, or call a tool
- Simulated service status and SQLite tickets
- Ticket create/update only after the confirmation card
- Prompt-injection screening and secret redaction
- A trace of stages and tool calls, without model prose
- An evaluation page for pass rate, latency, retrieval accuracy, and tool success

The spec review made a few rules explicit that the vibe notes only mention after the fact: retrieval is a tool rather than an automatic step, "yes" in chat is not confirmation, citations are appended by code, and the offline suite is not a live Claude score.

## Environment

Checked before building:

- Python 3.12.3, pip 24.0, no project packages installed
- `python3-venv` was missing and was installed so a virtual environment could be created
- No `.env` and no Azure key on the machine
- No database server; both apps use SQLite

Live Claude answers need `AZURE_ANTHROPIC_ENDPOINT`, `AZURE_ANTHROPIC_API_KEY`, and `AZURE_ANTHROPIC_MODEL` in a gitignored `.env`. See each project's `.env.example`. Tests and the no-key chat path do not need them. Without a key, the VPN question is answered from the local documents and the simulated status board, and no ticket is filed.

How long this takes to run: `pytest` is about a second per app. Starting Streamlit is a local command, not a separate service install.

## Run either app

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
streamlit run app.py
```

Run those commands inside `vibe-helpdesk` or `spec-helpdesk`.
