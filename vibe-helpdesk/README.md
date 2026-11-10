# Northstar IT Help Desk (vibe-coded)

This is the code-first demo. Behavior was settled in the Python modules, then checked with tests. The spec-driven twin lives in `../spec-helpdesk` and was specified before its code was written.

## What the environment already had

- Python 3.12.3 and pip 24.0
- No project virtual environment (`python3-venv` had to be installed)
- No `.env`, no Azure credentials, and no third-party project libraries
- No database server. SQLite ships with Python, so ticket storage stays on this machine

## What you need to add for live Claude answers

Copy `.env.example` to `.env` and set:

- `AZURE_ANTHROPIC_ENDPOINT` — Azure Anthropic base URL, usually ending in `/anthropic`
- `AZURE_ANTHROPIC_API_KEY` — key for that resource
- `AZURE_ANTHROPIC_MODEL` — deployment name

Do not commit `.env`. The app never writes the key into traces, errors, or `repr`.

Without those three values the chat still runs. It searches the local documents, reads the simulated service board, and refuses to file a ticket. The offline evaluation never calls Azure.

## Run

```bash
cd vibe-helpdesk
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
pytest
streamlit run app.py
```

Open Chat and choose **Try the VPN scenario**, or paste:

> My VPN keeps disconnecting. I am working remotely, and I have a client presentation in 30 minutes. Can you help?

Then open the trace under the answer, confirm a ticket only if a draft card appears, and run the suite on the Evaluation page.

## What was decided while building

- Retrieval, service status, and ticket drafts are model tools. A greeting can be answered with no tool call.
- `create_support_ticket` and `update_support_ticket` only stage a draft. The confirmation card is the only writer. A chat "yes" does not file anything.
- Obvious prompt-injection phrases are refused before the model sees them. Pasted passwords and MFA codes are redacted first.
- The trace stores the stage, a short summary, why that stage ran, and a small detail object. It does not store model prose.
- The agent stops after four tool rounds.
- If Azure is missing or the call fails, a fixed fallback quotes documents and status and still cannot create a ticket.
- Evaluation uses a scripted model so the numbers do not depend on the network. Retrieval accuracy is measured on the real TF-IDF index.

Those notes are retrospective. They were not a reviewed specification.
