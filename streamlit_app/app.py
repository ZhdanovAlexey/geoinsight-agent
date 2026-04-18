import os
import sys

# Ensure project root is on sys.path so "streamlit_app" is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from streamlit_app.chat import render_chat
from streamlit_app.client import GeoInsightClient

st.set_page_config(page_title="GeoInsight Agent", layout="wide")
st.title("GeoInsight Agent")

# Sidebar (TZ:14.5)
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

render_chat()
