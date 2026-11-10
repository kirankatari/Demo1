# Northstar IT Help Desk (spec-driven)

This copy was implemented from the approved documents in `specs/`. Behavior that contradicts those documents is a defect, not a shortcut. The code-first twin is `../vibe-helpdesk`.

Read these before changing code:

- `specs/requirements.md` — requirement ids, acceptance criteria, test ids
- `specs/architecture.md` — modules and the request path
- `specs/agent-design.md` — loop, tools, trace, fallback
- `specs/security.md` — injection rules and the confirmation gate
- `specs/evaluation.md` — offline cases and the dashboard contract
- `specs/implementation-plan.md` — milestone order
- `specs/review.md` — resolved decisions
- `specs/traceability-matrix.md` — requirement to test
- `specs/milestone-report.md` — what the test run actually did

## Environment this was built on

Python 3.12.3. No Azure credentials were present. `python3-venv` was not installed initially. SQLite from the standard library is the only database. Live answers need three variables in `.env`; tests and the offline chat do not.

## Configure

```bash
cd spec-helpdesk
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `AZURE_ANTHROPIC_ENDPOINT`, `AZURE_ANTHROPIC_API_KEY`, and `AZURE_ANTHROPIC_MODEL` in `.env` when you want Azure Claude. Do not commit `.env`.

## Run tests and the app

```bash
pytest
streamlit run app.py
```

`pytest` uses a scripted model and must pass with the Azure variables unset.

In the app, open Chat and press **Try the VPN scenario**. The trace sits under the answer. A ticket exists only after the confirmation card. The Evaluation page runs the offline suite and shows pass count, latency, retrieval accuracy, and tool success.

## Milestone acceptance

The implementation plan's exit check is a green `pytest` plus a manual pass through Chat, Tickets, and Evaluation. Results are in `specs/milestone-report.md`.
