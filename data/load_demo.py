"""ETL script: load demo CSV data into PostGIS.

Usage:
    uv run python data/load_demo.py --city Olmaliq --data-dir ./dataset
"""

import argparse
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg

TS_EPOCH = datetime(2014, 1, 1, tzinfo=timezone.utc)


def load_zones(cur: psycopg.Cursor, city: str, path: Path) -> int:
    count = 0
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            zid = int(row["zid"])
            wkt = row["wkt"]
            cur.execute(
                """
                INSERT INTO zones (zid, city, geom)
                VALUES (%s, %s, ST_GeomFromText(%s, 4326))
                ON CONFLICT (zid) DO NOTHING
                """,
                (zid, city, wkt),
            )
            count += 1
    return count


def load_demographics(cur: psycopg.Cursor, path: Path, valid_zids: set[int]) -> int:
    count = 0
    skipped = 0
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            zid = int(float(row["zid"]))
            if zid not in valid_zids:
                skipped += 1
                continue
            income = int(float(row["income"]))
            age = int(float(row["age"]))
            gender = int(float(row["gender"]))
            cnt = int(float(row["cnt"]))
            home_zid_raw = row.get("home_zid", "")
            job_zid_raw = row.get("job_zid", "")
            home_zid = (
                int(float(home_zid_raw)) if home_zid_raw and float(home_zid_raw) != 0 else None
            )
            job_zid = int(float(job_zid_raw)) if job_zid_raw and float(job_zid_raw) != 0 else None
            cur.execute(
                """
                INSERT INTO zone_demographics (zid, income, age, gender, cnt, home_zid, job_zid)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (zid, income, age, gender, cnt, home_zid, job_zid),
            )
            count += 1
    if skipped:
        print(f"  -> skipped {skipped} rows with unknown zids")
    return count


def load_dynamics(cur: psycopg.Cursor, path: Path, valid_zids: set[int]) -> int:
    count = 0
    skipped = 0
    batch = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            zid = int(row["zid"])
            if zid not in valid_zids:
                skipped += 1
                continue
            ts_hours = int(row["ts"])
            ts_dt = TS_EPOCH + timedelta(hours=ts_hours)
            batch.append(
                (
                    zid,
                    ts_dt,
                    int(float(row["income"])),
                    int(float(row["age"])),
                    int(float(row["gender"])),
                    int(float(row["cnt"])),
                )
            )
            count += 1
            if len(batch) >= 5000:
                _insert_dynamics_batch(cur, batch)
                batch.clear()
    if batch:
        _insert_dynamics_batch(cur, batch)
    if skipped:
        print(f"  -> skipped {skipped} rows with unknown zids")
    return count


def _insert_dynamics_batch(cur: psycopg.Cursor, batch: list[tuple]) -> None:
    cur.executemany(
        """
        INSERT INTO zone_dynamics (zid, ts, income, age, gender, cnt)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        batch,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Load demo data into PostGIS")
    parser.add_argument("--city", required=True, help="City name (e.g. Olmaliq)")
    parser.add_argument("--data-dir", required=True, help="Directory with CSV files")
    parser.add_argument(
        "--dsn",
        default="postgresql://geoinsight:geoinsight@localhost:5433/geoinsight",
        help="Postgres DSN",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    city_lower = args.city.lower()

    zones_file = data_dir / f"dim_zid_town_{args.city}.csv"
    demo_file = data_dir / f"geo_{city_lower}_cnt.csv"
    dyn_file = data_dir / f"geo_{city_lower}_dyn_all.csv"

    missing = [str(f) for f in [zones_file, demo_file, dyn_file] if not f.exists()]
    if missing:
        print(f"Missing files: {missing}", file=sys.stderr)
        sys.exit(1)

    with psycopg.connect(args.dsn) as conn:
        with conn.cursor() as cur:
            print(f"Loading zones from {zones_file}...")
            n = load_zones(cur, args.city, zones_file)
            print(f"  -> {n} zones")

            # Get valid zids for FK validation
            cur.execute("SELECT zid FROM zones")
            valid_zids = {row[0] for row in cur.fetchall()}

            print(f"Loading demographics from {demo_file}...")
            n = load_demographics(cur, demo_file, valid_zids)
            print(f"  -> {n} rows")

            print(f"Loading dynamics from {dyn_file}...")
            n = load_dynamics(cur, dyn_file, valid_zids)
            print(f"  -> {n} rows")

        conn.commit()
    print("Done.")


if __name__ == "__main__":
    main()
