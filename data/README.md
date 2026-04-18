# Demo Data

CSV files are not committed to git. Place them in this directory or `dataset/` at repo root.

## Required files for Olmaliq

| File | Description |
|---|---|
| `dim_zid_town_Olmaliq.csv` | Zone polygons (zid, city_id, net_type, wkt) |
| `geo_olmaliq_cnt.csv` | Zone demographics aggregate (zid, ts, income, age, gender, cnt, home_zid, job_zid) |
| `geo_olmaliq_dyn_all.csv` | Zone dynamics with time axis (zid, ts, income, age, gender, cnt) |

## Loading

```bash
uv run python data/load_demo.py --city Olmaliq --data-dir ./dataset
```
