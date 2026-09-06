"""Streamlit front end. This is the hosted URL judges will open."""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

import agent
import ch
import config
import extraction

st.set_page_config(page_title="The AD Room", page_icon="🎬", layout="wide")

SUGGESTIONS = [
    "Give me the overview and the three biggest scheduling risks.",
    "Build me a shooting schedule at five pages a day.",
    "Which scenes need the car, and can we shoot them together?",
    "Day Out of Days for the whole cast — who costs us the most days?",
    "How many night exteriors are there and what's driving the cost?",
]


@st.cache_data(ttl=30)
def load_overview():
    try:
        return tools_overview()
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def tools_overview():
    import tools

    return tools.project_overview()


if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

with st.sidebar:
    st.title("🎬 The AD Room")
    st.caption("Gemini + ADK + ClickHouse")

    uploaded = st.file_uploader("Upload a screenplay PDF", type="pdf")
    if uploaded and st.button("Break it down", type="primary", use_container_width=True):
        with st.status("Breaking down the script…", expanded=True) as status:
            st.write("Reading the PDF with Gemini…")
            data = extraction.extract_screenplay(uploaded.read())
            st.write(f"Found {len(data['scenes'])} scenes. Writing to ClickHouse…")
            stats = ch.replace_project(
                config.DEFAULT_PROJECT, data.get("title", uploaded.name), data["scenes"]
            )
            status.update(label=f"Loaded {stats['scenes']} scenes", state="complete")
        st.cache_data.clear()
        st.session_state.messages = []
        # New screenplay data means the agent's prior tool-call answers are stale —
        # start a fresh ADK session so it can't recall the old project from memory.
        st.session_state.session_id = str(uuid.uuid4())

    st.divider()
    overview = load_overview()
    if "error" in overview:
        st.error("Not connected to ClickHouse yet. Check your .env.")
    else:
        stats = overview.get("stats", {})
        st.metric("Loaded", overview.get("title", "—"))
        c1, c2 = st.columns(2)
        c1.metric("Scenes", stats.get("scenes", 0))
        c2.metric("Pages", stats.get("pages", 0))
        c1.metric("Night", stats.get("night_scenes", 0))
        c2.metric("Sets", stats.get("distinct_sets", 0))

st.header("Ask your First AD")

if "messages" not in st.session_state:
    st.session_state.messages = []

cols = st.columns(len(SUGGESTIONS))
pending = None
for col, suggestion in zip(cols, SUGGESTIONS):
    if col.button(suggestion, use_container_width=True):
        pending = suggestion

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message.get("tools"):
            st.caption("🔧 " + " → ".join(message["tools"]))
        st.markdown(message["content"])

typed = st.chat_input("e.g. which scenes can we shoot on the same day?")
question = typed or pending

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Checking the boards…"):
            try:
                result = agent.ask(question, session_id=st.session_state.session_id)
            except Exception as exc:  # noqa: BLE001
                result = {"answer": f"Something went wrong: `{exc}`", "tools_used": []}
        if result["tools_used"]:
            st.caption("🔧 " + " → ".join(result["tools_used"]))
        st.markdown(result["answer"])
    st.session_state.messages.append(
        {"role": "assistant", "content": result["answer"], "tools": result["tools_used"]}
    )
