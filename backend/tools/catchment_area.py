import time

import structlog
from agents import RunContextWrapper, function_tool

from backend.db.queries import query_catchment_area
from backend.tools.base import GeoContext
from backend.tools.find_zones import _calc_bbox

log = structlog.get_logger()


@function_tool
async def catchment_area(
    ctx: RunContextWrapper[GeoContext],
    zid: int,
    radius_m: int = 1000,
) -> dict:
    """Анализ зоны охвата — зоны в заданном радиусе с профилем аудитории.

    Args:
        zid: идентификатор центральной зоны
        radius_m: радиус в метрах (по умолчанию 1000)

    Returns:
        Количество зон в радиусе, суммарное население, список зон с расстоянием.
    """
    t0 = time.monotonic()
    zones = await query_catchment_area(zid=zid, radius_m=radius_m)
    duration_ms = int((time.monotonic() - t0) * 1000)

    log.info(
        "tool.catchment_area.done",
        trace_id=ctx.context.trace_id,
        zid=zid,
        radius_m=radius_m,
        zones_found=len(zones),
        duration_ms=duration_ms,
    )

    total_population = sum(z.total for z in zones)

    if zones:
        ctx.context.emit_artifact(
            {
                "type": "map",
                "viz": "choropleth",
                "geojson": {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": z.geometry_geojson,
                            "properties": {
                                "zid": z.zid,
                                "distance_m": z.distance_m,
                                "total": z.total,
                            },
                        }
                        for z in zones
                    ],
                },
                "color_metric": "total",
                "legend": {
                    "title": f"Население в радиусе {radius_m}м от зоны {zid}",
                    "min": 0,
                    "max": max(z.total for z in zones) if zones else 1,
                },
                "bbox": _calc_bbox(zones),
                "tooltip_fields": ["zid", "distance_m", "total"],
            }
        )

        # Table artifact
        table_rows = [[z.zid, z.distance_m, z.total] for z in zones[:20]]
        ctx.context.emit_artifact(
            {
                "type": "table",
                "title": f"Зоны в радиусе {radius_m}м от {zid}",
                "columns": ["zid", "расстояние (м)", "население"],
                "rows": table_rows,
            }
        )

    return {
        "center_zid": zid,
        "radius_m": radius_m,
        "zones_in_radius": len(zones),
        "total_population": total_population,
        "top_zones": [
            {"zid": z.zid, "distance_m": z.distance_m, "total": z.total} for z in zones[:5]
        ],
    }
