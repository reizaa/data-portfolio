"""Customer & revenue retention cohorts for "Leafy", a fictional online plant shop.

Answers: of the customers who first bought in month M, how many come back and how much
revenue do they keep generating (Net Revenue Retention) in the months after?
"""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1] / "data" / "plant_shop_orders.csv"
OUT = HERE / "output"; OUT.mkdir(exist_ok=True)

df = pd.read_csv(DATA, parse_dates=["order_date"])
df["revenue"] = df["qty"] * df["unit_price"]
df["month"] = df["order_date"].dt.to_period("M")
df["cohort"] = df.groupby("customer_id")["month"].transform("min")
df["age"] = (df["month"] - df["cohort"]).apply(lambda x: x.n)

# Customer retention: share of the cohort active N months after the first order.
active = df.groupby(["cohort", "age"])["customer_id"].nunique().unstack(fill_value=0)
cust_ret = active.div(active[0], axis=0)

# Revenue retention: cohort revenue in month N relative to its first month.
rev = df.groupby(["cohort", "age"])["revenue"].sum().unstack(fill_value=0)
rev_ret = rev.div(rev[0], axis=0)

# Mask cells that are in the future for younger cohorts.
last = df["month"].max()
for c in cust_ret.index:
    future = [a for a in cust_ret.columns if (c + a) > last]
    cust_ret.loc[c, future] = None
    rev_ret.loc[c, future] = None


def heatmap(mat, title, path, max_age=12):
    m = mat.iloc[:, : max_age + 1]
    fig, ax = plt.subplots(figsize=(11, 6.5))
    vmax = 0.6 if "Customer" in title else 1.0
    im = ax.imshow(m.values.astype(float), cmap="Greens", vmin=0, vmax=vmax, aspect="auto")
    ax.set_xticks(range(m.shape[1]), [f"M{a}" for a in m.columns])
    ax.set_yticks(range(m.shape[0]), [str(c) for c in m.index])
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            v = m.iat[i, j]
            if pd.notna(v) and j > 0:
                ax.text(j, i, f"{v:.0%}", ha="center", va="center", fontsize=7,
                        color="white" if v > 0.55 * vmax else "#1f2937")
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold")
    ax.set_xlabel("Months since first order"); ax.set_ylabel("First-order cohort")
    fig.colorbar(im, ax=ax, fraction=0.025, format=lambda x, _: f"{x:.0%}")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


heatmap(cust_ret, "Customer retention by cohort", OUT / "customer_retention.png")
heatmap(rev_ret, "Net revenue retention by cohort", OUT / "revenue_retention.png")

# Headline numbers per segment (city) — month-3 retention, cohorts old enough only.
mature = df[df["cohort"] <= last - 3]
def m3(g):
    base = g.loc[g.age == 0, "customer_id"].nunique()
    return g.loc[g.age == 3, "customer_id"].nunique() / base
seg = mature.groupby("city").apply(m3, include_groups=False).sort_values(ascending=False)

avg_m1 = cust_ret[1].mean(); avg_m3 = cust_ret[3].mean(); nrr6 = rev_ret[6].mean()
summary = (f"Average M1 customer retention: {avg_m1:.1%}\n"
           f"Average M3 customer retention: {avg_m3:.1%}\n"
           f"Average M6 net revenue retention: {nrr6:.1%}\n\n"
           "M3 retention by city:\n" + "\n".join(f"  {c:12s} {v:.1%}" for c, v in seg.items()))
# ---------------------------------------------------------------------------
# BEFORE vs AFTER: refreshing the report.
# Each month the report is rebuilt from a new data snapshot and numbers in old
# cohorts change. BEFORE: two heatmaps side by side and someone hunts for the
# differences by eye. AFTER: every changed cell is listed with its cause.
import time
rng = pd.Series(range(len(df)), index=df.index).sample(frac=0.03, random_state=3).index
prev = df.drop(index=rng)                                   # last month's snapshot: 3% of orders not synced yet
edited = prev.sample(n=40, random_state=4).index
prev.loc[edited, "revenue"] = (prev.loc[edited, "revenue"] * 0.9).round()   # prices later corrected

t0 = time.perf_counter()
key = ["cohort", "age"]
a = prev.groupby(key)["revenue"].sum(); b = df.groupby(key)["revenue"].sum()
diff = (b - a.reindex(b.index, fill_value=0))
changed = diff[diff.abs() > 0]
late = df.loc[rng].groupby(key)["revenue"].sum().reindex(changed.index, fill_value=0)
fix = (df.loc[edited, "revenue"] - prev.loc[edited, "revenue"]).groupby(
    [df.loc[edited, "cohort"], df.loc[edited, "age"]]).sum().reindex(changed.index, fill_value=0)
explained = ((late + fix - changed).abs() < 1).mean()
expl = pd.DataFrame({"change": changed, "late_orders": late, "price_corrections": fix})
expl.sort_values("change", key=abs, ascending=False).to_csv(OUT / "snapshot_change_explained.csv")
secs = time.perf_counter() - t0

summary += (f"\n\nBEFORE vs AFTER (monthly refresh validation)\n"
            f"  cells that changed vs last snapshot: {len(changed)} of {len(b)}\n"
            f"  before: found by comparing two heatmaps by eye, cause unknown\n"
            f"  after:  {explained:.0%} of changed cells explained automatically "
            f"(late-synced orders vs price corrections) in {secs:.2f} s")
(OUT / "summary.txt").write_text(summary)
print(summary)
