from agents import RunContextWrapper, function_tool

from backend.tools.base import GeoContext


@function_tool
async def compare_zones(
    ctx: RunContextWrapper[GeoContext],
    zids: list[int],
) -> dict:
    """Сравнение 2-5 зон по демографии и трафику.

    Args:
        zids: список zid для сравнения (2-5 штук)
    """
    return {"status": "not_implemented"}
