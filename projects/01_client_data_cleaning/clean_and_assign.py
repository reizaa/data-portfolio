"""Client master data for "Ruang Kerja", a fictional coworking space.

Two branches export payments in different formats (date style, currency, name
spelling, duplicate rows). This pipeline:
  1. cleans and standardizes the raw payments into one table
  2. builds a monthly subscription status per client:
     new, active, churned, reactivated, churned_again
  3. assigns every paying client to an account manager by branch, balancing
     workload by monthly revenue and respecting each manager's capacity
  4. writes data-quality checks so every fix is auditable
"""
from pathlib import Path
import re
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1] / "data"
OUT = HERE / "output"; OUT.mkdir(exist_ok=True)
USD_IDR = 16_000

raw = pd.read_csv(DATA / "coworking_payments_raw.csv")
checks = {"raw rows": len(raw)}

# 0. BEFORE: the old way — paste both exports into one sheet and use them as-is --
old = raw.copy()
old["paid_on"] = pd.to_datetime(old.paid_on, format="mixed", dayfirst=True)   # one guess for all
old["amount_idr"] = old.amount.astype(str).str.replace(r"[^\d]", "", regex=True).astype(int)  # "937.50 USD" -> 93,750
before_stats = {
    "clients counted": old.company.nunique(),
    "total revenue (IDR)": old.amount_idr.sum(),
    "duplicate rows kept": int(old.duplicated(["company", "paid_on", "amount"]).sum()),
}

# 1. Clean ------------------------------------------------------------------
df = raw.copy()
df["company"] = (df.company.str.strip().str.replace(r"\s+", " ", regex=True)
                 .str.replace(r"^PT\s+", "", regex=True, flags=re.I).str.title())
df["plan"] = df.plan.str.title()
# Each source has its own date style; parse per source instead of guessing.
DATE_FORMATS = {"jakarta_pos": "%d/%m/%Y", "bali_sheet": "%Y-%m-%d"}
df["paid_on"] = pd.concat([pd.to_datetime(g.paid_on, format=DATE_FORMATS[s], errors="coerce")
                           for s, g in df.groupby("source")])


def to_idr(v):
    v = str(v)
    if v.endswith("USD"):
        return round(float(v.split()[0]) * USD_IDR)
    return int(re.sub(r"[^\d]", "", v))


df["amount_idr"] = df.amount.map(to_idr)
checks["company spellings before -> after"] = f"{raw.company.nunique()} -> {df.company.nunique()}"
before = len(df)
df = df.drop_duplicates(subset=["company", "paid_on", "amount_idr"])
checks["duplicate rows removed"] = before - len(df)
df["month"] = df.paid_on.dt.to_period("M")
df["branch"] = df.source.map({"jakarta_pos": "Jakarta", "bali_sheet": "Bali"})
clean = df[["company", "branch", "plan", "seats", "paid_on", "month", "amount_idr"]].sort_values(["company", "paid_on"])
clean.to_csv(OUT / "payments_clean.csv", index=False)

# 2. Subscription status per client per month --------------------------------
months = pd.period_range(clean.month.min(), clean.month.max(), freq="M")
paid = clean.groupby(["company", "month"]).amount_idr.sum().unstack().reindex(columns=months)
status_rows = []
for company, row in paid.iterrows():
    seen, churns, prev = False, 0, False
    for m in months:
        now = pd.notna(row[m])
        if now and not seen:          s = "new"
        elif now and prev:            s = "active"
        elif now and not prev:        s = "reactivated"
        elif not now and prev:
            churns += 1;              s = "churned" if churns == 1 else "churned_again"
        else:                         s = None
        seen |= now; prev = now
        if s:
            status_rows.append({"company": company, "month": str(m), "status": s,
                                "mrr_idr": row[m] if now else 0})
status = pd.DataFrame(status_rows)
status.to_csv(OUT / "subscription_status.csv", index=False)
monthly = status.pivot_table(index="month", columns="status", values="company", aggfunc="count", fill_value=0)

# 3. Account-manager assignment ----------------------------------------------
last = str(months[-1])
current = (status[(status.month == last) & (status.mrr_idr > 0)]
           .merge(clean[["company", "branch"]].drop_duplicates(), on="company")
           .sort_values("mrr_idr", ascending=False))
ams = pd.read_csv(DATA / "account_managers.csv")
load = {a: 0 for a in ams.account_manager}
count = {a: 0 for a in ams.account_manager}
cap = dict(zip(ams.account_manager, ams.max_accounts))
assign = []
for _, c in current.iterrows():           # biggest accounts first, to the least-loaded AM
    pool = [a for a in ams[ams.branch == c.branch].account_manager if count[a] < cap[a]]
    am = min(pool, key=lambda a: load[a]) if pool else "UNASSIGNED (capacity full)"
    if pool:
        load[am] += c.mrr_idr; count[am] += 1
    assign.append({"company": c.company, "branch": c.branch, "mrr_idr": int(c.mrr_idr),
                   "status": c.status, "account_manager": am})
assign = pd.DataFrame(assign)
assign.to_csv(OUT / "am_assignment.csv", index=False)
book = assign.groupby("account_manager").agg(clients=("company", "size"), mrr_idr=("mrr_idr", "sum"))

# 4. Data-quality checks -------------------------------------------------------
checks["clean rows"] = len(clean)
checks["unparsed dates"] = int(clean.paid_on.isna().sum())
checks["clients"] = clean.company.nunique()
checks["paying clients in " + last] = len(current)

# BEFORE vs AFTER -------------------------------------------------------------
wrong_month = int((old.paid_on.dt.to_period("M").values != df.reindex(old.index).month.values)[
    df.reindex(old.index).month.notna().values].sum())
# Old way: every spelling is its own "client", so one company can sit with several AMs.
split = raw.assign(clean=raw.company.str.strip().str.replace(r"\s+", " ", regex=True)
                   .str.replace(r"^PT\s+", "", regex=True, flags=re.I).str.title())
split_clients = int((split.groupby("clean").company.nunique() > 1).sum())
true_rev = clean.amount_idr.sum()
ba = pd.DataFrame({
    "before (as-is)": [before_stats["clients counted"], f"Rp{before_stats['total revenue (IDR)']/1e6:,.0f}jt",
                       before_stats["duplicate rows kept"], wrong_month, split_clients],
    "after (pipeline)": [clean.company.nunique(), f"Rp{true_rev/1e6:,.0f}jt", 0, 0, 0],
}, index=["clients counted", "total revenue", "duplicate payments", "payments in the wrong month",
          "clients split across several names (-> several AMs)"])
rev_err = before_stats["total revenue (IDR)"] / true_rev - 1

lines = ["BEFORE vs AFTER", ba.to_string(), f"Revenue error of the old way: {rev_err:+.0%}", ""]
lines += ["Data-quality checks:"] + [f"  {k}: {v}" for k, v in checks.items()]
lines += ["", "Subscription status per month:", monthly.to_string(), "",
          f"Account-manager book of business ({last}):",
          book.to_string(formatters={"mrr_idr": lambda x: f"Rp{x/1e6:,.1f}jt"})]
(OUT / "summary.txt").write_text("\n".join(lines))
print("\n".join(lines))
