"""Streamlit smoke test for the chat shell. FR-CHAT-01."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def test_app_renders_chat():
    app = AppTest.from_file(str(APP), default_timeout=40)
    app.run()
    assert not app.exception, app.exception
    text = " ".join(block.value for block in app.markdown)
    assert "IT Help Desk" in text
    assert app.chat_input
