import os
import sys

# Ensure project root is on sys.path so "streamlit_app" is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from streamlit_app.chat import render_chat
from streamlit_app.client import GeoInsightClient

st.set_page_config(page_title="GeoInsight Agent", layout="wide")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("GeoInsight Agent")
    st.caption("AI-аналитик геоданных мобильного оператора")

    backend_url = st.text_input(
        "Backend URL",
        value=os.environ.get("BACKEND_URL", "http://localhost:8080"),
    )

    st.divider()

    # Instruments
    st.markdown("#### Инструменты")
    st.markdown(
        """
| | Инструмент |
|---|---|
| :mag: | **Поиск зон** — по возрасту, доходу, полу |
| :busts_in_silhouette: | **Демография** — детальный профиль зоны |
| :bar_chart: | **Трафик** — почасовая динамика |
| :world_map: | **Поиск по адресу** — улица → зона |
| :radio: | **Зона охвата** — население в радиусе |
| :scales: | **Сравнение** — 2-5 зон рядом |
| :construction: | ~~Потоки дом-работа~~ — *скоро* |
| :construction: | ~~Роуминг~~ — *скоро* |
"""
    )

    st.divider()

    # Suggestions
    st.markdown("#### Примеры запросов")

    SUGGESTIONS = [
        "Где открыть кофейню для аудитории 25-35 в Олмалике?",
        "Какая демография зоны 4277303?",
        "Покажи трафик по часам в зоне 4267953",
        "Найди топ-10 зон с высоким доходом в Олмалике",
        "Сколько людей в радиусе 2 км от зоны 4277303?",
        "Сравни зоны 4277303 и 4267953",
        "Найди зону возле улицы Навои в Олмалике",
    ]

    for i, suggestion in enumerate(SUGGESTIONS):
        if st.button(suggestion, key=f"suggest_{i}", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": suggestion})
            st.session_state.pending = True
            st.rerun()

    st.divider()

    # Capabilities / limitations
    with st.expander("Возможности и ограничения"):
        st.markdown(
            """
**Города:** Олмалик, Ташкент

**Зоны:** ~250x250 м, числовой ID (zid).
Можно искать по адресу — агент найдёт ближайшую зону.

**Фильтры демографии:**
- Возраст: <18, 18-25, 26-35, 36-45, 46-60, >60
- Доход: низкий → очень высокий (6 уровней)
- Пол: мужской / женский

**Не поддерживается пока:**
- Потоки дом-работа (нет данных)
- Анализ роуминга/туристов (нет данных)
- Поиск по произвольному полигону
"""
        )

    if st.button("Очистить чат", use_container_width=True, type="secondary"):
        st.session_state.messages = []
        st.session_state.pop("pending", None)
        st.rerun()


# ── Init state ───────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending" not in st.session_state:
    st.session_state.pending = False
if "client" not in st.session_state or st.session_state.get("_backend_url") != backend_url:
    st.session_state.client = GeoInsightClient(base_url=backend_url)
    st.session_state._backend_url = backend_url


# ── Main area ────────────────────────────────────────────────────────────────
if not st.session_state.messages:
    st.markdown("## Привет! Я — GeoInsight Agent")
    st.markdown(
        "Помогу проанализировать геоданные мобильного оператора: "
        "демография, трафик, зоны охвата. "
        "Задайте вопрос или выберите пример из боковой панели слева."
    )

render_chat()
