import time

import structlog
from agents import RunContextWrapper, function_tool

from backend.db.queries import query_find_zones
from backend.tools.base import GeoContext

log = structlog.get_logger()


@function_tool
async def find_zones(
    ctx: RunContextWrapper[GeoContext],
    city: str,
    age: list[int] | None = None,
    income: list[int] | None = None,
    gender: list[int] | None = None,
    min_total: int | None = None,
    top_n: int = 20,
) -> dict:
    """Найти зоны (~250x250м), удовлетворяющие критериям демографии.

    Args:
        city: название города (например, "Olmaliq", "Tashkent")
        age: список возрастных групп 0-5 (0=<18, 1=18-25, 2=26-35, 3=36-45, 4=46-60, 5=>60)
        income: список категорий дохода 0-6 (0=неизвестно, 1=низкий, ..., 6=очень высокий)
        gender: список 0 (м) или 1 (ж)
        min_total: минимум суммарного населения зоны
        top_n: количество лучших зон в результате

    Returns:
        Сводка для LLM — количество найденных зон и топ-5 с метриками (без полигонов).
    """
    t0 = time.monotonic()
    zones = await query_find_zones(
        city=city,
        age=age,
        income=income,
        gender=gender,
        min_total=min_total,
        top_n=top_n,
    )
    duration_ms = int((time.monotonic() - t0) * 1000)

    log.info(
        "tool.find_zones.done",
        trace_id=ctx.context.trace_id,
        rows=len(zones),
        duration_ms=duration_ms,
    )

    if zones:
        bbox = _calc_bbox(zones)
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
                                "score": z.score,
                                "total": z.total,
                            },
                        }
                        for z in zones
                    ],
                },
                "color_metric": "score",
                "legend": {"title": "Рейтинг зоны", "min": 0, "max": 10},
                "bbox": bbox,
                "tooltip_fields": ["zid", "score", "total"],
            }
        )

    return {
        "count": len(zones),
        "top": [{"zid": z.zid, "score": z.score, "total": z.total} for z in zones[:5]],
        "summary": f"Найдено {len(zones)} зон в {city}",
    }


def _calc_bbox(zones: list) -> list[float]:
    """Calculate bounding box from zone GeoJSON geometries."""
    lons, lats = [], []
    for z in zones:
        geom = z.geometry_geojson
        if geom.get("type") == "Polygon":
            for ring in geom.get("coordinates", []):
                for coord in ring:
                    lons.append(coord[0])
                    lats.append(coord[1])
    if not lons:
        return [69.5, 40.8, 69.8, 41.0]
    return [min(lons), min(lats), max(lons), max(lats)]
