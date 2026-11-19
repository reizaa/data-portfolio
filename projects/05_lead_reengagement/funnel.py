"""Lead funnel & re-engagement list for "LinguaPlus", a fictional language school.

Input is an event log (one row per funnel step). The script rebuilds each lead's
journey, measures conversion per acquisition channel, and produces a prioritized
list of leads worth contacting again (cold, lost after trial, or dropped out).
"""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1] / "data" / "language_school_events.csv"
OUT = HERE / "output"; OUT.mkdir(exist_ok=True)
TODAY = pd.Timestamp("2026-06-30")

ev = pd.read_csv(DATA, parse_dates=["event_time"])

# One row per lead: when did each step happen?
journey = ev.pivot_table(index="lead_id", columns="event", values="event_time", aggfunc="min")
meta = ev.groupby("lead_id")[["channel", "course"]].first()
j = meta.join(journey)


def status(r):
    if pd.notna(r.get("dropped_out")): return "dropped_out"
    if pd.notna(r.get("enrolled")):    return "active_student"
    if pd.notna(r.get("trial_class")): return "lost_after_trial"
    if pd.notna(r.get("no_response")): return "cold_no_response"
    return "open_inquiry"


j["status"] = j.apply(status, axis=1)
j["last_touch"] = journey.max(axis=1)
j["days_since"] = (TODAY - j["last_touch"]).dt.days

# Funnel by channel
f = j.groupby("channel").agg(inquiries=("status", "size"),
                             trials=("trial_class", "count"),
                             enrolled=("enrolled", "count"))
f["trial_rate"] = f.trials / f.inquiries
f["enroll_rate"] = f.enrolled / f.inquiries
f = f.sort_values("enroll_rate", ascending=False)

fig, ax = plt.subplots(figsize=(9, 4.5))
x = range(len(f))
ax.bar(x, f.inquiries, color="#cbd5e1", label="Inquiries")
ax.bar(x, f.trials, color="#60a5fa", label="Trial class")
ax.bar(x, f.enrolled, color="#1d4ed8", label="Enrolled")
ax.set_xticks(list(x), f.index)
for i, (_, r) in enumerate(f.iterrows()):
    ax.text(i, r.inquiries + 8, f"{r.enroll_rate:.0%} enroll", ha="center", fontsize=9)
ax.set_title("Funnel by acquisition channel", loc="left", fontweight="bold")
ax.spines[["top", "right"]].set_visible(False); ax.legend(frameon=False)
fig.tight_layout(); fig.savefig(OUT / "funnel_by_channel.png", dpi=130); plt.close(fig)

# Re-engagement list: score = how warm the lead was x how recent x channel quality.
warmth = {"lost_after_trial": 3, "dropped_out": 2, "cold_no_response": 1, "open_inquiry": 1}
pool = j[j.status.isin(warmth) & j.days_since.between(14, 240)].copy()
pool["score"] = (pool.status.map(warmth)
                 * (1 - pool.days_since / 300)
                 * pool.channel.map(f.enroll_rate / f.enroll_rate.max())).round(3)
pool["suggested_message"] = pool.status.map({
    "lost_after_trial": "Free second trial class + 10% early-bird",
    "dropped_out": "Resume-where-you-left-off offer",
    "cold_no_response": "New schedule announcement",
    "open_inquiry": "Reminder with course brochure",
})
cols = ["channel", "course", "status", "days_since", "score", "suggested_message"]
pool.sort_values("score", ascending=False)[cols].to_csv(OUT / "reengagement_list.csv")

# BEFORE vs AFTER: with a budget of 300 follow-up calls, the old way was a blast
# to random non-students. Simulate who would actually come back (hidden truth,
# noisier than the score) and compare the two strategies.
import numpy as np
rng = np.random.default_rng(11)
base_p = pool.status.map({"lost_after_trial": .22, "dropped_out": .15, "cold_no_response": .05, "open_inquiry": .07})
recency = np.exp(-pool.days_since / 120)
chan = pool.channel.map({"Referral": 1.3, "Walk-in": 1.3, "Google Search": 1.0}).fillna(.7)
truth = rng.random(len(pool)) < (base_p * recency * chan * rng.uniform(.6, 1.4, len(pool))).clip(0, 1)
pool["would_return"] = truth
BUDGET = 300
random_hits = np.mean([pool.sample(BUDGET, random_state=s).would_return.sum() for s in range(200)])
scored_hits = pool.nlargest(BUDGET, "score").would_return.sum()
ba = (f"BEFORE vs AFTER (budget {BUDGET} calls, simulated responses)\n"
      f"  before: random blast  -> {random_hits:.0f} leads come back\n"
      f"  after:  top-scored    -> {scored_hits} leads come back ({scored_hits / random_hits:.1f}x)")

summary = [ba, "", "Funnel by channel:", f[["inquiries", "trials", "enrolled", "enroll_rate"]].to_string(
               formatters={"enroll_rate": "{:.1%}".format}), "",
           "Lead status:", j.status.value_counts().to_string(), "",
           f"Re-engagement list: {len(pool):,} leads (top 10 below)",
           pool.sort_values("score", ascending=False)[cols].head(10).to_string()]
(OUT / "summary.txt").write_text("\n".join(summary))
print("\n".join(summary))
