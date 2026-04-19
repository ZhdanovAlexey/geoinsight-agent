import time

import structlog
from agents import RunContextWrapper, function_tool

from backend.db.queries import query_compare_zones
from backend.tools.base import GeoContext
from backend.tools.zone_demographics import AGE_LABELS, INCOME_LABELS

log = structlog.get_logger()


@function_tool
async def compare_zones(
    ctx: RunContextWrapper[GeoContext],
    zids: list[int],
) -> dict:
    """Сравнение 2-5 зон по демографии и трафику.

    Args:
        zids: список zid для сравнения (2-5 штук)

    Returns:
        Таблица сравнения зон по населению, доходу, возрасту, полу и пиковому часу.
    """
    t0 = time.monotonic()
    rows = await query_compare_zones(zids[:5])
    duration_ms = int((time.monotonic() - t0) * 1000)

    log.info(
        "tool.compare_zones.done",
        trace_id=ctx.context.trace_id,
        zids=zids,
        rows=len(rows),
        duration_ms=duration_ms,
    )

    # Build comparison table
    table_rows = []
    for r in rows:
        top_income = max(r.by_income, key=r.by_income.get) if r.by_income else None
        top_age = max(r.by_age, key=r.by_age.get) if r.by_age else None
        male_pct = round(r.by_gender.get(0, 0) / r.total * 100, 1) if r.total else 0
        table_rows.append(
            [
                r.zid,
                r.total,
                INCOME_LABELS.get(top_income, "?") if top_income is not None else "?",
                AGE_LABELS.get(top_age, "?") if top_age is not None else "?",
                f"{male_pct}%",
                f"{r.peak_hour:02d}:00" if r.peak_hour is not None else "?",
                r.peak_traffic or 0,
            ]
        )

    ctx.context.emit_artifact(
        {
            "type": "table",
            "title": f"Сравнение зон: {', '.join(str(z) for z in zids)}",
            "columns": [
                "zid",
                "население",
                "доминирующий доход",
                "доминирующий возраст",
                "мужчин %",
                "пик-час",
                "трафик в пик",
            ],
            "rows": table_rows,
        }
    )

    return {
        "zones_compared": len(rows),
        "comparison": [
            {
                "zid": r.zid,
                "total": r.total,
                "top_income": INCOME_LABELS.get(max(r.by_income, key=r.by_income.get), "?")
                if r.by_income
                else "?",
                "top_age": AGE_LABELS.get(max(r.by_age, key=r.by_age.get), "?")
                if r.by_age
                else "?",
                "peak_hour": r.peak_hour,
                "peak_traffic": r.peak_traffic,
            }
            for r in rows
        ],
    }
