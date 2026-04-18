import time

import httpx
import structlog
from agents import RunContextWrapper, function_tool

from backend.db.queries import query_nearest_zone
from backend.tools.base import GeoContext

log = structlog.get_logger()

CITY_COUNTRY = {
    "Olmaliq": "Olmaliq, Tashkent Region, Uzbekistan",
    "Tashkent": "Tashkent, Uzbekistan",
}


@function_tool
async def geocode_zone(
    ctx: RunContextWrapper[GeoContext],
    address: str,
    city: str = "Olmaliq",
) -> dict:
    """Найти ближайшую зону по адресу, улице или ориентиру.

    Args:
        address: адрес, улица или название ориентира (например, «ул. Навои» или «базар»)
        city: город (Olmaliq или Tashkent)

    Returns:
        Ближайшая зона (zid) к указанному адресу с расстоянием в метрах.
    """
    t0 = time.monotonic()

    city_suffix = CITY_COUNTRY.get(city, f"{city}, Uzbekistan")
    search_query = f"{address}, {city_suffix}"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": search_query, "format": "json", "limit": 1},
                headers={"User-Agent": "GeoInsight-Agent/1.0"},
            )
            results = resp.json()
    except Exception as exc:
        log.warning("tool.geocode_zone.nominatim_error", error=str(exc))
        return {"error": f"Ошибка геокодирования: {exc}"}

    if not results:
        return {"error": f"Адрес не найден: {address} ({city})"}

    lat = float(results[0]["lat"])
    lon = float(results[0]["lon"])
    display_name = results[0].get("display_name", address)

    zone = await query_nearest_zone(lat=lat, lon=lon, city=city)
    duration_ms = int((time.monotonic() - t0) * 1000)

    log.info(
        "tool.geocode_zone.done",
        trace_id=ctx.context.trace_id,
        address=address,
        lat=lat,
        lon=lon,
        zid=zone.zid if zone else None,
        duration_ms=duration_ms,
    )

    if not zone:
        return {
            "address": display_name,
            "lat": lat,
            "lon": lon,
            "error": "Зоны не найдены в этом городе",
        }

    return {
        "address": display_name,
        "lat": lat,
        "lon": lon,
        "zid": zone.zid,
        "distance_m": zone.distance_m,
        "total": zone.total,
    }
