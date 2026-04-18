
import streamlit as st

from streamlit_app.artifacts import render_artifact


def render_chat() -> None:
    """Render chat history and handle new input."""
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            # Show tool steps if present
            if msg.get("tool_steps"):
                _render_tool_steps(msg["tool_steps"])
            st.markdown(msg["content"])
            for art in msg.get("artifacts", []):
                render_artifact(art)
            if msg.get("langfuse_url"):
                st.caption(f"[Trace в Langfuse]({msg['langfuse_url']})")

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
        tool_steps = []
        trace_url = None

        for ev in st.session_state.client.stream_chat(
            [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
        ):
            if ev.event == "trace_started":
                if isinstance(ev.data, dict):
                    trace_url = ev.data.get("langfuse_url")

            elif ev.event == "tool_call":
                if isinstance(ev.data, dict):
                    tool_steps.append(ev.data)
                    name = ev.data.get("name", "?")
                    args = ev.data.get("args", {})
                    with status:
                        st.write(f"**{name}** `{_summarize_args(args)}`")

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

        status.update(label="Готово", state="complete", expanded=False)

        # Render tool steps
        if tool_steps:
            _render_tool_steps(tool_steps)

        text_placeholder.markdown(text)

        for art in artifacts:
            render_artifact(art)

        if trace_url:
            st.caption(f"[Trace в Langfuse]({trace_url})")

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": text,
                "artifacts": artifacts,
                "tool_steps": tool_steps,
                "langfuse_url": trace_url,
            }
        )


def _render_tool_steps(steps: list[dict]) -> None:
    """Render tool call steps in an expander."""
    with st.expander(f"Шаги агента ({len(steps)})", expanded=False):
        for i, step in enumerate(steps, 1):
            name = step.get("name", "?")
            args = step.get("args", {})
            output = step.get("output")

            st.markdown(f"**{i}. {name}**")

            cols = st.columns(2)
            with cols[0]:
                st.caption("Аргументы")
                st.json(args, expanded=False)
            with cols[1]:
                st.caption("Результат")
                if output:
                    if isinstance(output, dict):
                        st.json(output, expanded=False)
                    else:
                        st.code(str(output)[:500])
                else:
                    st.info("Нет данных")

            if i < len(steps):
                st.divider()


def _summarize_args(args: dict) -> str:
    items = []
    for k, v in args.items():
        if isinstance(v, list) and len(v) > 5:
            items.append(f"{k}=[{len(v)} items]")
        else:
            items.append(f"{k}={v}")
    return ", ".join(items)
