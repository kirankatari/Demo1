# Northstar Technologies IT Help Desk

Two builds of the same fictional IT support assistant, for the Vibe Coding vs. Spec-Driven Coding exercise.

An employee can ask:

> My VPN keeps disconnecting. I am working remotely, and I have a client presentation in 30 minutes. Can you help?

The assistant searches local IT documents, checks a simulated service status, explains what it did, asks a clarifying question when the device is unknown, and drafts a ticket. The ticket is written to SQLite only after the employee confirms it.

| Demo | Path | What it is |
| --- | --- | --- |
| Demo 1, vibe coding | `demo1_vibe/` | One Streamlit module. Retrieval, tools, the agent, and the pages are in `helpdesk_app.py`. |
| Demo 2, spec-driven | `specs/` and `demo2_spec/` | Requirements, architecture, agent design, security, evaluation, and an implementation plan, then a modular app that follows them. |

Both apps stay on this machine except for the optional Azure Claude call. Neither app contains an API key.

## Environment that was on this machine

- Ubuntu 24.04, Python 3.12.3, pip 24.0
- The repository had only a title in `README.md`
- No project virtual environment, no installed app libraries, and no `.env`

`python3-venv` was installed so a virtual environment could be created. Dependencies are pinned in each demo's `requirements.txt`. The virtual environment is gitignored.

## What you need to add for live Claude

Create a `.env` file in this folder (it is gitignored). Start from `.env.example`:

```text
AZURE_CLAUDE_ENDPOINT=https://YOUR_RESOURCE.services.ai.azure.com/anthropic/v1/messages
AZURE_CLAUDE_API_KEY=your-key
AZURE_CLAUDE_MODEL=your-model-or-deployment-name
AZURE_CLAUDE_API_VERSION=2023-06-01
AZURE_CLAUDE_AUTH_STYLE=api-key
```

`AZURE_CLAUDE_ENDPOINT` must be the full Anthropic Messages URL. Use `x-api-key` or `bearer` for `AZURE_CLAUDE_AUTH_STYLE` if the gateway does not want the `api-key` header.

Without those three values the apps still run. They say they are in local mode and answer from the documents and the simulated status file. Automated tests never call Azure.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r demo2_spec/requirements.txt
pytest
streamlit run demo2_spec/streamlit_app.py
```

The vibe app uses the same libraries:

```bash
streamlit run demo1_vibe/helpdesk_app.py --server.port 8502
```

In Chat, use **Try the sample VPN question**. The reply should cite the VPN troubleshooting document, report the VPN as degraded, ask which device you are using, and show a draft ticket. Choose **Confirm** before anything appears on the Tickets page. The trace under the chat lists the stages and tool calls. Open Evaluation and run the suite to see pass rate, latency, and tool success. That suite uses scripted model replies.

## How the two builds differ

Demo 1 was built as a single program aimed at the demo path. Its tests cover retrieval, the sample VPN turn, confirmation, injection, and the small evaluation report.

Demo 2 started from the documents in `specs/`. `specs/review.md` records the closed decisions and the requirements-to-tests matrix. The running code splits the model client from retrieval, tickets, and the confirmation gate. Requirement ids in those documents map to `demo2_spec/tests/` and to `demo2_spec/northstar/eval/cases.json`. The evaluation page runs that same case file.

Shared product rules, so the comparison is about structure rather than different behavior:

- TF-IDF over the markdown corpus. No vector database.
- The model may search, check status, or draft a ticket. It has no tool that writes a ticket.
- A draft is stored only after **Confirm**, or after a chat reply that is only an exact confirmation phrase such as `yes`.
- Messages that try to override the rules are refused before any tool runs.
- Traces show stage names and tool outcomes, not provider thinking text.

## Decisions already made

These were open in the brief and are closed in `specs/review.md`:

- Azure is the Anthropic Messages API. The key, endpoint, and model come only from the environment.
- One local employee, named in the sidebar. No company login.
- The app must remain usable when the API key is missing.
- Ticket edits wait for confirmation, same as new tickets.
- Chat memory lasts for the browser session. Tickets stay in the local SQLite file.
