from dataclasses import dataclass

import sqlalchemy as sa

from backend.db.engine import engine


@dataclass
class ZoneResult:
    zid: int
    score: float
    total: int
    geometry_geojson: dict


@dataclass
class DemographicRow:
    income: int
    age: int
    gender: int
    cnt: int


@dataclass
class TrafficRow:
    hour: int
    cnt: int


async def query_find_zones(
    city: str,
    age: list[int] | None = None,
    income: list[int] | None = None,
    gender: list[int] | None = None,
    min_total: int | None = None,
    top_n: int = 20,
) -> list[ZoneResult]:
    """Find zones matching demographic criteria, ranked by score."""
    conditions = ["z.city = :city"]
    params: dict = {"city": city, "top_n": top_n}

    if age:
        conditions.append("zd.age = ANY(:age)")
        params["age"] = age
    if income:
        conditions.append("zd.income = ANY(:income)")
        params["income"] = income
    if gender:
        conditions.append("zd.gender = ANY(:gender)")
        params["gender"] = gender

    where = " AND ".join(conditions)

    having = ""
    if min_total:
        having = "HAVING SUM(zd.cnt) >= :min_total"
        params["min_total"] = min_total

    sql = sa.text(f"""
        SELECT
            z.zid,
            SUM(zd.cnt) AS total,
            ST_AsGeoJSON(z.geom)::json AS geometry_geojson
        FROM zones z
        JOIN zone_demographics zd ON zd.zid = z.zid
        WHERE {where}
        GROUP BY z.zid, z.geom
        {having}
        ORDER BY total DESC
        LIMIT :top_n
    """)

    async with engine.connect() as conn:
        rows = (await conn.execute(sql, params)).mappings().all()

    max_total = rows[0]["total"] if rows else 1
    return [
        ZoneResult(
            zid=r["zid"],
            score=round(r["total"] / max_total * 10, 2),
            total=r["total"],
            geometry_geojson=r["geometry_geojson"],
        )
        for r in rows
    ]


async def query_zone_demographics(
    zid: int,
    income: list[int] | None = None,
    age: list[int] | None = None,
    gender: list[int] | None = None,
) -> list[DemographicRow]:
    """Get demographic breakdown for a zone."""
    conditions = ["zid = :zid"]
    params: dict = {"zid": zid}

    if income:
        conditions.append("income = ANY(:income)")
        params["income"] = income
    if age:
        conditions.append("age = ANY(:age)")
        params["age"] = age
    if gender:
        conditions.append("gender = ANY(:gender)")
        params["gender"] = gender

    where = " AND ".join(conditions)

    sql = sa.text(f"""
        SELECT income, age, gender, SUM(cnt) AS cnt
        FROM zone_demographics
        WHERE {where}
        GROUP BY income, age, gender
        ORDER BY cnt DESC
    """)

    async with engine.connect() as conn:
        rows = (await conn.execute(sql, params)).mappings().all()

    return [
        DemographicRow(income=r["income"], age=r["age"], gender=r["gender"], cnt=r["cnt"])
        for r in rows
    ]


async def query_zone_traffic(
    zid: int,
    hours: list[int] | None = None,
) -> list[TrafficRow]:
    """Get hourly traffic for a zone from dynamics data."""
    conditions = ["zid = :zid"]
    params: dict = {"zid": zid}

    hour_filter = ""
    if hours:
        hour_filter = "HAVING EXTRACT(HOUR FROM ts)::int = ANY(:hours)"
        params["hours"] = hours

    sql = sa.text(f"""
        SELECT EXTRACT(HOUR FROM ts)::int AS hour, SUM(cnt) AS cnt
        FROM zone_dynamics
        WHERE {" AND ".join(conditions)}
        GROUP BY hour
        {hour_filter}
        ORDER BY hour
    """)

    async with engine.connect() as conn:
        rows = (await conn.execute(sql, params)).mappings().all()

    return [TrafficRow(hour=r["hour"], cnt=r["cnt"]) for r in rows]
