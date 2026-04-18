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


@dataclass
class ZoneComparisonRow:
    zid: int
    total: int
    by_income: dict
    by_age: dict
    by_gender: dict
    peak_hour: int | None
    peak_traffic: int | None


async def query_compare_zones(zids: list[int]) -> list[ZoneComparisonRow]:
    """Get demographic and traffic summary for multiple zones."""
    results = []
    for zid in zids:
        # Demographics
        demo_sql = sa.text("""
            SELECT income, age, gender, SUM(cnt) AS cnt
            FROM zone_demographics
            WHERE zid = :zid
            GROUP BY income, age, gender
        """)
        async with engine.connect() as conn:
            demo_rows = (await conn.execute(demo_sql, {"zid": zid})).mappings().all()

        total = sum(r["cnt"] for r in demo_rows)
        by_income: dict[int, int] = {}
        by_age: dict[int, int] = {}
        by_gender: dict[int, int] = {}
        for r in demo_rows:
            by_income[r["income"]] = by_income.get(r["income"], 0) + r["cnt"]
            by_age[r["age"]] = by_age.get(r["age"], 0) + r["cnt"]
            by_gender[r["gender"]] = by_gender.get(r["gender"], 0) + r["cnt"]

        # Traffic peak
        traffic_sql = sa.text("""
            SELECT EXTRACT(HOUR FROM ts)::int AS hour, SUM(cnt) AS cnt
            FROM zone_dynamics
            WHERE zid = :zid
            GROUP BY hour
            ORDER BY cnt DESC
            LIMIT 1
        """)
        async with engine.connect() as conn:
            traffic_row = (await conn.execute(traffic_sql, {"zid": zid})).mappings().first()

        peak_hour = traffic_row["hour"] if traffic_row else None
        peak_traffic = traffic_row["cnt"] if traffic_row else None

        results.append(
            ZoneComparisonRow(
                zid=zid,
                total=total,
                by_income=by_income,
                by_age=by_age,
                by_gender=by_gender,
                peak_hour=peak_hour,
                peak_traffic=peak_traffic,
            )
        )
    return results


@dataclass
class NearestZone:
    zid: int
    distance_m: float
    total: int


async def query_nearest_zone(
    lat: float,
    lon: float,
    city: str = "Olmaliq",
) -> NearestZone | None:
    """Find the nearest zone to a lat/lon point."""
    sql = sa.text("""
        SELECT
            z.zid,
            ST_Distance(
                z.centroid::geography,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            ) AS distance_m,
            COALESCE(SUM(zd.cnt), 0) AS total
        FROM zones z
        LEFT JOIN zone_demographics zd ON zd.zid = z.zid
        WHERE z.city = :city
        GROUP BY z.zid, z.centroid
        ORDER BY z.centroid <-> ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
        LIMIT 1
    """)

    async with engine.connect() as conn:
        row = (await conn.execute(sql, {"lat": lat, "lon": lon, "city": city})).mappings().first()

    if not row:
        return None

    return NearestZone(
        zid=row["zid"],
        distance_m=round(row["distance_m"], 0),
        total=row["total"],
    )


@dataclass
class CatchmentZone:
    zid: int
    distance_m: float
    total: int
    geometry_geojson: dict


async def query_catchment_area(
    zid: int,
    radius_m: int = 1000,
) -> list[CatchmentZone]:
    """Find all zones within radius_m of the given zone's centroid."""
    sql = sa.text("""
        WITH center AS (
            SELECT centroid FROM zones WHERE zid = :zid
        )
        SELECT
            z.zid,
            ST_Distance(z.centroid::geography, c.centroid::geography) AS distance_m,
            COALESCE(SUM(zd.cnt), 0) AS total,
            ST_AsGeoJSON(z.geom)::json AS geometry_geojson
        FROM zones z
        CROSS JOIN center c
        LEFT JOIN zone_demographics zd ON zd.zid = z.zid
        WHERE ST_DWithin(z.centroid::geography, c.centroid::geography, :radius_m)
        GROUP BY z.zid, z.geom, z.centroid, c.centroid
        ORDER BY distance_m
    """)

    async with engine.connect() as conn:
        rows = (await conn.execute(sql, {"zid": zid, "radius_m": radius_m})).mappings().all()

    return [
        CatchmentZone(
            zid=r["zid"],
            distance_m=round(r["distance_m"], 0),
            total=r["total"],
            geometry_geojson=r["geometry_geojson"],
        )
        for r in rows
    ]
