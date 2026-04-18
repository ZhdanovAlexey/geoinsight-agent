import pandas as pd
import pydeck as pdk
import streamlit as st


def render_artifact(art: dict) -> None:
    """Dispatch artifact rendering by type."""
    t = art.get("type")
    if t == "map":
        _render_map(art)
    elif t == "flow_map":
        _render_flow_map(art)
    elif t == "table":
        _render_table(art)
    elif t == "chart":
        _render_chart(art)
    else:
        st.warning(f"Unknown artifact type: {t}")


def _render_map(art: dict) -> None:
    geojson = art.get("geojson", {})
    color_metric = art.get("color_metric")

    features = geojson.get("features", [])
    values = [f["properties"].get(color_metric, 0) for f in features] if color_metric else []
    vmin = min(values) if values else 0
    vmax = max(values) if values else 1
    denom = vmax - vmin if vmax > vmin else 1

    layer = pdk.Layer(
        "GeoJsonLayer",
        data=geojson,
        get_fill_color=(
            f"[255 * (properties.{color_metric} - {vmin}) / {denom}, 100, 50, 180]"
            if color_metric
            else [100, 150, 200, 180]
        ),
        get_line_color=[0, 0, 0],
        line_width_min_pixels=1,
        pickable=True,
        auto_highlight=True,
    )

    bbox = art.get("bbox")
    if bbox and len(bbox) == 4:
        view_state = pdk.ViewState(
            longitude=(bbox[0] + bbox[2]) / 2,
            latitude=(bbox[1] + bbox[3]) / 2,
            zoom=12,
        )
    else:
        view_state = pdk.ViewState(longitude=69.6, latitude=40.85, zoom=12)

    tooltip_fields = art.get("tooltip_fields", [])
    tooltip_html = "<br/>".join(f"<b>{f}:</b> {{{f}}}" for f in tooltip_fields)

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip={"html": tooltip_html} if tooltip_html else None,
        map_style="light",
    )
    st.pydeck_chart(deck)

    legend = art.get("legend")
    if legend:
        st.caption(f"{legend.get('title', '')}: {legend.get('min', 0)} — {legend.get('max', 10)}")


def _render_flow_map(art: dict) -> None:
    flows = art.get("flows", [])
    if not flows:
        st.info("No flow data")
        return

    layer = pdk.Layer(
        "ArcLayer",
        data=flows,
        get_source_position="from",
        get_target_position="to",
        get_width="weight",
        get_source_color=[0, 128, 255],
        get_target_color=[255, 0, 128],
        pickable=True,
    )

    bbox = art.get("bbox")
    if bbox and len(bbox) == 4:
        view_state = pdk.ViewState(
            longitude=(bbox[0] + bbox[2]) / 2,
            latitude=(bbox[1] + bbox[3]) / 2,
            zoom=11,
        )
    else:
        view_state = pdk.ViewState(longitude=69.6, latitude=40.85, zoom=11)

    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state))


def _render_table(art: dict) -> None:
    title = art.get("title")
    if title:
        st.subheader(title)
    columns = art.get("columns", [])
    rows = art.get("rows", [])
    if columns and rows:
        df = pd.DataFrame(rows, columns=columns)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No table data")


def _render_chart(art: dict) -> None:
    title = art.get("title")
    if title:
        st.subheader(title)
    data = art.get("data", {})
    labels = data.get("labels", [])
    values = data.get("values", [])
    chart_type = art.get("chart_type", "bar")

    if labels and values:
        df = pd.DataFrame({"label": labels, "value": values}).set_index("label")
        if chart_type == "line":
            st.line_chart(df)
        else:
            st.bar_chart(df)
    else:
        st.info("No chart data")
