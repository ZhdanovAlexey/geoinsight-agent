from agents import RunContextWrapper, function_tool

from backend.tools.base import GeoContext


@function_tool
async def roaming_analysis(
    ctx: RunContextWrapper[GeoContext],
    city: str,
    roaming_type: str = "Международный",
    country: str | None = None,
) -> dict:
    """Анализ визитов по роумингу — количество, география, время.

    Args:
        city: город для анализа
        roaming_type: тип роуминга ("Международный", "Внутрисетевой")
        country: страна (опционально, для фильтрации)
    """
    return {"status": "not_implemented"}
