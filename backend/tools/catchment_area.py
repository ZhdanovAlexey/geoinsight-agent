from agents import RunContextWrapper, function_tool

from backend.tools.base import GeoContext


@function_tool
async def catchment_area(
    ctx: RunContextWrapper[GeoContext],
    zid: int,
    radius_m: int = 1000,
) -> dict:
    """Анализ зоны охвата — зоны в заданном радиусе с профилем аудитории.

    Args:
        zid: идентификатор центральной зоны
        radius_m: радиус в метрах
    """
    return {"status": "not_implemented"}
