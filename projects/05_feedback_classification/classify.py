"""Topic classification of hotel guest reviews.

Two-stage approach used for categorizing free text at scale:
  1. a transparent keyword rule layer (fast, free, explainable)
  2. anything the rules cannot decide is sent to an LLM with a fixed rubric
     (prompt in prompt_template.md; not called here so the repo runs offline)
The rules are evaluated against hand-labelled data with precision / recall per topic.
"""
from pathlib import Path
import re
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[1] / "data" / "hotel_reviews.csv"
OUT = HERE / "output"; OUT.mkdir(exist_ok=True)

RULES = {
    "cleanliness": r"clean|dust|dirty|spotless|housekeeping|towel|sheet",
    "staff": r"staff|reception|front desk|concierge|rude|friendly",
    "food": r"breakfast|buffet|restaurant|dinner|room service|nasi|tasted",
    "location": r"beach|city center|station|walking distance|location|taxi",
    "price": r"value|expensive|price|fee|deal|money",
}


def classify(text):
    hits = {t: len(re.findall(p, text.lower())) for t, p in RULES.items()}
    best = max(hits.values())
    winners = [t for t, h in hits.items() if h == best]
    if best == 0 or len(winners) > 1:
        return "needs_llm"
    return winners[0]


df = pd.read_csv(DATA)
df["pred"] = df.text.map(classify)
decided = df[df.pred != "needs_llm"]

rows = []
for t in RULES:
    tp = ((decided.pred == t) & (decided.label == t)).sum()
    fp = ((decided.pred == t) & (decided.label != t)).sum()
    fn = ((decided.pred != t) & (decided.label == t)).sum()
    rows.append({"topic": t, "precision": tp / (tp + fp) if tp + fp else 0,
                 "recall": tp / (tp + fn) if tp + fn else 0, "support": int((df.label == t).sum())})
ev = pd.DataFrame(rows).set_index("topic")

# Topic x sentiment view (stars as a proxy) — what to fix first.
df["topic"] = df.pred.where(df.pred != "needs_llm", df.label)
pain = df.assign(negative=df.stars <= 2).groupby("topic").agg(
    reviews=("review_id", "size"), negative_share=("negative", "mean")).sort_values("negative_share", ascending=False)

summary = [f"Reviews: {len(df)} | decided by rules: {len(decided)/len(df):.1%} | sent to LLM: {(df.pred=='needs_llm').mean():.1%}",
           f"Rule-layer accuracy on decided reviews: {(decided.pred == decided.label).mean():.1%}", "",
           ev.to_string(float_format="{:.2f}".format), "", "Negative share by topic:",
           pain.to_string(formatters={"negative_share": "{:.0%}".format})]
df.drop(columns="topic").to_csv(OUT / "classified_reviews.csv", index=False)
(OUT / "summary.txt").write_text("\n".join(summary))
print("\n".join(summary))
