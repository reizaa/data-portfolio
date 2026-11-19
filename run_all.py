"""Regenerate every dataset, run all six projects, and copy charts for the web page."""
from pathlib import Path
import shutil, subprocess, sys

ROOT = Path(__file__).resolve().parent
STEPS = [
    "data/generate.py",
    "projects/01_retention_cohort/analysis.py",
    "projects/02_query_optimization/benchmark.py",
    "projects/03_daily_change_alert/alert.py",
    "projects/04_lead_reengagement/funnel.py",
    "projects/05_feedback_classification/classify.py",
    "projects/06_client_data_cleaning/clean_and_assign.py",
]
for s in STEPS:
    print(f"\n=== {s}")
    subprocess.run([sys.executable, str(ROOT / s)], check=True)

img = ROOT / "docs" / "img"; img.mkdir(parents=True, exist_ok=True)
for png in (ROOT / "projects").glob("*/output/*.png"):
    shutil.copy(png, img / png.name)
print("\nDone. Open docs/index.html in a browser.")
