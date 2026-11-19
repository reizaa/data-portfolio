"""Daily sales change alert for "Kopi Senja", a fictional coffee chain.

Every morning: compare yesterday with the same weekday last week (fair comparison,
weekends are busier), find the stores/items that moved the total the most, flag
anomalies, and write a short chat-ready message. Designed to run on a scheduler
(cron, n8n, GitHub Actions) and post to a team channel.
"""
from pathlib import Path
import sys
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")  # message uses •, →, — ; keep Windows consoles happy

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1] / "data" / "coffee_daily_sales.csv"
OUT = HERE / "output"; OUT.mkdir(exist_ok=True)

df = pd.read_csv(DATA, parse_dates=["date"])
day = pd.Timestamp(sys.argv[1]) if len(sys.argv) > 1 else df["date"].max()
ref = day - pd.Timedelta(days=7)

cur = df[df.date == day].groupby(["store", "item"])["revenue"].sum()
prev = df[df.date == ref].groupby(["store", "item"])["revenue"].sum()
chg = pd.DataFrame({"today": cur, "last_week": prev}).fillna(0)
chg["diff"] = chg.today - chg.last_week

total_now, total_prev = chg.today.sum(), chg.last_week.sum()

# Anomaly rule: a store is flagged when its revenue is outside mean ± 3 sd of the
# same weekday over the previous 6 weeks.
hist = df[(df.date < day) & (df.date.dt.dayofweek == day.dayofweek)]
hist = hist.groupby(["store", "date"])["revenue"].sum().groupby("store").agg(["mean", "std"])
store_now = df[df.date == day].groupby("store")["revenue"].sum()
z = ((store_now - hist["mean"]) / hist["std"]).dropna()
flags = z[z.abs() > 3]

store_diff = chg.groupby("store")["diff"].sum().sort_values()
top_items = chg["diff"].abs().sort_values(ascending=False).head(5).index


def rp(x):
    return f"Rp{x/1e6:,.2f}jt" if abs(x) >= 1e6 else f"Rp{x/1e3:,.0f}rb"


pct = (total_now / total_prev - 1) * 100
msg = [f"*Kopi Senja daily sales — {day:%a %d %b %Y}* (vs {ref:%a %d %b})",
       f"Total revenue {rp(total_now)} ({pct:+.1f}%, {rp(total_now - total_prev)})", ""]
if len(flags):
    msg.append(":rotating_light: *Anomalies* (beyond 3 sd of the same weekday):")
    for s, v in flags.items():
        msg.append(f"  • {s}: {rp(store_now[s])}, {v:+.1f} sd from normal")
    msg.append("")
msg.append("*Biggest movers (store · item)*")
for s, i in top_items:
    r = chg.loc[(s, i)]
    msg.append(f"  • {s} · {i}: {rp(r['diff'])} ({rp(r['last_week'])} → {rp(r['today'])})")
msg += ["", f"Largest drop: {store_diff.index[0]} ({rp(store_diff.iloc[0])}) · "
            f"Largest gain: {store_diff.index[-1]} ({rp(store_diff.iloc[-1])})"]

text = "\n".join(msg)

# BEFORE vs AFTER: the old daily message was only the total. How much of the
# movement does the new message actually explain?
explained = chg.loc[top_items, "diff"].abs().sum() / chg["diff"].abs().sum()
anomaly_hits = len(flags)
ba = (f"BEFORE: 'Total revenue {rp(total_now)} ({pct:+.1f}%)' — 0 stores/items named, 0 anomalies flagged\n"
      f"AFTER:  {len(top_items)} named movers covering {explained:.0%} of all item-level movement "
      f"(out of {len(chg)} store-item pairs), {anomaly_hits} anomalies flagged automatically")
(OUT / "before_after.txt").write_text(ba, encoding="utf-8")
print(ba + "\n")
(OUT / f"alert_{day:%Y-%m-%d}.md").write_text(text, encoding="utf-8")
print(text)

# Export for the interactive web page -------------------------------------------
import json
(OUT / "web.json").write_text(json.dumps({
    "before": f"Kopi Senja daily sales — {day:%a %d %b %Y}\nTotal revenue {rp(total_now)} ({pct:+.1f}%)",
    "after": text.replace("*", "").replace(":rotating_light: ", ""),
    "explained": round(float(explained), 3), "anomalies": int(anomaly_hits)}, ensure_ascii=False), encoding="utf-8")
