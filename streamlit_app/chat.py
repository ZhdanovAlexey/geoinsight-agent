import streamlit as st

from streamlit_app.artifacts import render_artifact


def render_chat() -> None:
    """Render chat history and handle new input."""
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            for art in msg.get("artifacts", []):
                render_artifact(art)

    user_input = st.chat_input("Спросите про геоданные...")
    if not user_input:
        return

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        status = st.status("Думаю...", expanded=True)
        text_placeholder = st.empty()
        text = ""
        artifacts = []
        trace_url = None

        for ev in st.session_state.client.stream_chat(
            [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
        ):
            if ev.event == "trace_started":
                if isinstance(ev.data, dict):
                    trace_url = ev.data.get("langfuse_url")

            elif ev.event == "tool_started":
                if isinstance(ev.data, dict):
                    with status:
                        st.write(
                            f"**{ev.data.get('name', '?')}** — "
                            f"`{_summarize_args(ev.data.get('args', {}))}`"
                        )
                        status.update(label=f"Выполняю {ev.data.get('name', '')}...")

            elif ev.event == "tool_finished":
                if isinstance(ev.data, dict):
                    with status:
                        st.write(f"Готово за {ev.data.get('duration_ms', '?')}мс")

            elif ev.event == "tool_failed":
                if isinstance(ev.data, dict):
                    with status:
                        st.error(f"Ошибка: {ev.data.get('error', '?')}")

            elif ev.event == "artifact":
                if isinstance(ev.data, dict):
                    artifacts.append(ev.data)

            elif ev.event is None:
                if isinstance(ev.data, dict):
                    try:
                        delta = ev.data["choices"][0]["delta"].get("content", "")
                        if delta:
                            text += delta
                            text_placeholder.markdown(text + "...")
                    except (KeyError, IndexError):
                        pass

        text_placeholder.markdown(text)
        status.update(label="Готово", state="complete", expanded=False)

        for art in artifacts:
            render_artifact(art)

        if trace_url:
            st.caption(f"[Trace в Langfuse]({trace_url})")

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": text,
                "artifacts": artifacts,
            }
        )


def _summarize_args(args: dict) -> str:
    items = []
    for k, v in args.items():
        if isinstance(v, list) and len(v) > 5:
            items.append(f"{k}=[{len(v)} items]")
        else:
            items.append(f"{k}={v}")
    return ", ".join(items)
