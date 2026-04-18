import time

import structlog
from agents import RunContextWrapper, function_tool

from backend.db.queries import query_zone_traffic
from backend.tools.base import GeoContext

log = structlog.get_logger()


@function_tool
async def zone_traffic(
    ctx: RunContextWrapper[GeoContext],
    zid: int,
    hours: list[int] | None = None,
) -> dict:
    """Почасовая динамика трафика в зоне.

    Args:
        zid: идентификатор зоны
        hours: список часов 0-23 для фильтрации (опционально)

    Returns:
        Почасовое распределение трафика, пиковый час и значение.
    """
    t0 = time.monotonic()
    rows = await query_zone_traffic(zid=zid, hours=hours)
    duration_ms = int((time.monotonic() - t0) * 1000)

    log.info(
        "tool.zone_traffic.done",
        trace_id=ctx.context.trace_id,
        zid=zid,
        rows=len(rows),
        duration_ms=duration_ms,
    )

    by_hour = {r.hour: r.cnt for r in rows}
    peak_hour = max(by_hour, key=by_hour.get, default=0) if by_hour else 0
    peak_value = by_hour.get(peak_hour, 0)

    ctx.context.emit_artifact(
        {
            "type": "chart",
            "chart_type": "bar",
            "title": f"Трафик зоны {zid} по часам",
            "data": {
                "labels": [f"{h:02d}:00" for h in sorted(by_hour.keys())],
                "values": [by_hour[h] for h in sorted(by_hour.keys())],
            },
        }
    )

    return {
        "zid": zid,
        "by_hour": by_hour,
        "peak_hour": peak_hour,
        "peak_value": peak_value,
    }
