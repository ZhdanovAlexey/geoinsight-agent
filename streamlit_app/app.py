import os
import sys

# Ensure project root is on sys.path so "streamlit_app" is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from streamlit_app.chat import render_chat
from streamlit_app.client import GeoInsightClient

st.set_page_config(page_title="GeoInsight Agent", layout="wide")
st.title("GeoInsight Agent")

# Sidebar
with st.sidebar:
    backend_url = st.text_input(
        "Backend URL",
        value=os.environ.get("BACKEND_URL", "http://localhost:8080"),
    )

    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()

# Init state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "client" not in st.session_state or st.session_state.get("_backend_url") != backend_url:
    st.session_state.client = GeoInsightClient(base_url=backend_url)
    st.session_state._backend_url = backend_url

# Suggestion chips (before first message)
SUGGESTIONS = [
    "Где открыть кофейню для аудитории 25-35 в Олмалике?",
    "Какая демография зоны 4277303?",
    "Покажи трафик по часам в зоне 4267953",
    "Найди топ-10 зон с высоким доходом в Олмалике",
    "Сколько людей живёт в радиусе 2 км от зоны 4277303?",
    "Сравни зоны 4277303 и 4267953 по демографии",
]

if not st.session_state.messages:
    st.markdown("##### Попробуйте спросить:")
    cols = st.columns(3)
    for i, suggestion in enumerate(SUGGESTIONS):
        with cols[i % 3]:
            if st.button(suggestion, key=f"suggest_{i}", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": suggestion})
                st.rerun()

render_chat()
