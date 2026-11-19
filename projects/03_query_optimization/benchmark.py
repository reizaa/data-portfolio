"""Query optimization on 3 million weather-sensor readings (SQLite).

Same business question, three approaches:
  1. naive      - full scan with a function on the filter column
  2. indexed    - sargable range filter + composite index
  3. summary    - pre-aggregated hourly table (the idea behind materialized views)
Each approach must return identical numbers before its speed counts.
"""
from pathlib import Path
import sqlite3, time
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "output"; OUT.mkdir(exist_ok=True)
DB = OUT / "sensors.sqlite"

N_ROWS = 3_000_000
rng = np.random.default_rng(7)

if DB.exists():
    DB.unlink()
con = sqlite3.connect(DB)
stations = pd.read_csv(ROOT / "data" / "weather_stations.csv")
stations.to_sql("stations", con, index=False)

print(f"Generating {N_ROWS:,} readings ...")
start = pd.Timestamp("2026-01-01").value // 10**9
ts = start + rng.integers(0, 180 * 86400, N_ROWS)
readings = pd.DataFrame({
    "station_id": rng.choice(stations.station_id, N_ROWS),
    "ts": pd.to_datetime(ts, unit="s").strftime("%Y-%m-%d %H:%M:%S"),
    "temp_c": rng.normal(27, 4, N_ROWS).round(2),
    "humidity": rng.uniform(40, 99, N_ROWS).round(1),
})
readings.to_sql("readings", con, index=False, chunksize=200_000)
con.commit()

QUESTION = "Average temperature & max humidity per region, 1-14 March 2026"

NAIVE = """
SELECT s.region, ROUND(AVG(r.temp_c), 3) AS avg_temp, MAX(r.humidity) AS max_hum
FROM readings r JOIN stations s ON s.station_id = r.station_id
WHERE date(r.ts) BETWEEN '2026-03-01' AND '2026-03-14'
GROUP BY s.region ORDER BY s.region"""

INDEXED = """
SELECT s.region, ROUND(AVG(r.temp_c), 3) AS avg_temp, MAX(r.humidity) AS max_hum
FROM readings r JOIN stations s ON s.station_id = r.station_id
WHERE r.ts >= '2026-03-01' AND r.ts < '2026-03-15'
GROUP BY s.region ORDER BY s.region"""

SUMMARY = """
SELECT s.region, ROUND(SUM(h.temp_sum) / SUM(h.n), 3) AS avg_temp, MAX(h.max_hum) AS max_hum
FROM readings_hourly h JOIN stations s ON s.station_id = h.station_id
WHERE h.hour >= '2026-03-01' AND h.hour < '2026-03-15'
GROUP BY s.region ORDER BY s.region"""


def timed(sql, runs=3):
    best, res = 1e9, None
    for _ in range(runs):
        t = time.perf_counter(); res = con.execute(sql).fetchall(); best = min(best, time.perf_counter() - t)
    return best, res


results = {}
results["1. naive full scan"] = timed(NAIVE)

con.execute("CREATE INDEX idx_readings_ts ON readings(ts, station_id, temp_c, humidity)")
results["2. sargable filter + covering index"] = timed(INDEXED)

con.executescript("""
CREATE TABLE readings_hourly AS
SELECT station_id, substr(ts, 1, 13) || ':00:00' AS hour,
       SUM(temp_c) AS temp_sum, COUNT(*) AS n, MAX(humidity) AS max_hum
FROM readings GROUP BY station_id, hour;
CREATE INDEX idx_hourly ON readings_hourly(hour, station_id);
""")
results["3. pre-aggregated hourly table"] = timed(SUMMARY)

baseline_time, baseline_rows = results["1. naive full scan"]
lines = [f"Question: {QUESTION}", f"Rows scanned by naive query: {N_ROWS:,}", ""]
for name, (t, rows) in results.items():
    same = "same result" if rows == baseline_rows else "RESULT MISMATCH"
    lines.append(f"{name:38s} {t*1000:8.1f} ms   {baseline_time/t:6.1f}x   {same}")
lines += ["", "Result:"] + [f"  {r}" for r in baseline_rows]
report = "\n".join(lines)
(OUT / "benchmark.txt").write_text(report)
print(report)
import json
(OUT / "web.json").write_text(json.dumps({"rows": N_ROWS, "question": QUESTION,
    "runs": [{"name": n.split(". ", 1)[1], "ms": round(t * 1000, 1), "same": r == baseline_rows} for n, (t, r) in results.items()]}))
con.close()
DB.unlink()  # keep the repo small; rerun to rebuild
