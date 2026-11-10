# Demo 1 — vibe-coded help desk

`helpdesk_app.py` is the whole application: chat, TF-IDF search, simulated status, ticket drafts, the confirmation gate, and the evaluation page.

```bash
streamlit run demo1_vibe/helpdesk_app.py --server.port 8502
```

Run that from the repository root. It does not import the spec-driven package. Azure settings are the same `.env` values described in the repository README. Without them, the sample VPN question still runs in local mode.
