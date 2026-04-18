from agents import RunContextWrapper, function_tool

from backend.tools.base import GeoContext


@function_tool
async def home_work_flow(
    ctx: RunContextWrapper[GeoContext],
    zid: int,
    direction: str = "both",
    top_n: int = 10,
) -> dict:
    """Анализ потоков дом-работа для зоны.

    Args:
        zid: идентификатор зоны
        direction: направление потока — "from_home", "to_work", "both"
        top_n: количество топ-зон в результате
    """
    return {"status": "not_implemented"}
