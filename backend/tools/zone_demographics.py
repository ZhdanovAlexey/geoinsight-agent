import time

import structlog
from agents import RunContextWrapper, function_tool

from backend.db.queries import query_zone_demographics
from backend.tools.base import GeoContext

log = structlog.get_logger()

AGE_LABELS = {0: "<18", 1: "18-25", 2: "26-35", 3: "36-45", 4: "46-60", 5: ">60"}
INCOME_LABELS = {
    0: "неизвестно",
    1: "низкий",
    2: "ниже среднего",
    3: "средний",
    4: "выше среднего",
    5: "высокий",
    6: "очень высокий",
}
GENDER_LABELS = {0: "мужской", 1: "женский"}


@function_tool
async def zone_demographics(
    ctx: RunContextWrapper[GeoContext],
    zid: int,
    income: list[int] | None = None,
    age: list[int] | None = None,
    gender: list[int] | None = None,
) -> dict:
    """Демографический профиль зоны — распределение по доходу, возрасту, полу.

    Args:
        zid: идентификатор зоны
        income: фильтр по категориям дохода 0-6
        age: фильтр по возрастным группам 0-5
        gender: фильтр по полу — 0 (м) или 1 (ж)

    Returns:
        Распределение населения зоны по категориям.
    """
    t0 = time.monotonic()
    rows = await query_zone_demographics(zid=zid, income=income, age=age, gender=gender)
    duration_ms = int((time.monotonic() - t0) * 1000)

    log.info(
        "tool.zone_demographics.done",
        trace_id=ctx.context.trace_id,
        zid=zid,
        rows=len(rows),
        duration_ms=duration_ms,
    )

    total = sum(r.cnt for r in rows)

    by_income: dict[str, int] = {}
    by_age: dict[str, int] = {}
    by_gender: dict[str, int] = {}

    for r in rows:
        label = INCOME_LABELS.get(r.income, str(r.income))
        by_income[label] = by_income.get(label, 0) + r.cnt

        label = AGE_LABELS.get(r.age, str(r.age))
        by_age[label] = by_age.get(label, 0) + r.cnt

        label = GENDER_LABELS.get(r.gender, str(r.gender))
        by_gender[label] = by_gender.get(label, 0) + r.cnt

    table_rows = []
    for r in rows[:20]:
        table_rows.append(
            [
                r.income,
                INCOME_LABELS.get(r.income, "?"),
                r.age,
                AGE_LABELS.get(r.age, "?"),
                GENDER_LABELS.get(r.gender, "?"),
                r.cnt,
            ]
        )

    ctx.context.emit_artifact(
        {
            "type": "table",
            "title": f"Демография зоны {zid}",
            "columns": ["income_code", "income", "age_code", "age", "gender", "cnt"],
            "rows": table_rows,
        }
    )

    return {
        "zid": zid,
        "total": total,
        "by_income": by_income,
        "by_age": by_age,
        "by_gender": by_gender,
    }
