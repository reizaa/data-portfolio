"""Generate all synthetic datasets used in this portfolio.

Every dataset is fictional and produced from a fixed random seed, so results are
reproducible. Run:  python data/generate.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
rng = np.random.default_rng(42)


# 1. "Leafy" — an online plant shop. One row per order line.
def plant_shop_orders():
    products = {
        "Monstera": 189_000, "Snake Plant": 95_000, "Pothos": 55_000, "Fiddle Leaf Fig": 245_000,
        "Peace Lily": 120_000, "Ceramic Pot": 75_000, "Potting Mix 5L": 40_000, "Plant Food": 35_000,
    }
    cities = ["Jakarta", "Bandung", "Surabaya", "Yogyakarta", "Medan", "Denpasar"]
    months = pd.period_range("2025-01", "2026-06", freq="M")
    rows, cid = [], 0
    for m_idx, month in enumerate(months):
        for _ in range(int(rng.integers(140, 220))):          # new customers this month
            cid += 1
            city = rng.choice(cities)
            loyalty = rng.beta(2, 5)                            # how likely they come back
            for later in months[m_idx:]:
                first = later == month
                if not first and rng.random() > loyalty:
                    continue
                n_orders = 1 if first else int(rng.integers(1, 3))
                for _ in range(n_orders):
                    day = int(rng.integers(1, later.days_in_month + 1))
                    oid = f"ORD-{len(rows):06d}"
                    for p in rng.choice(list(products), size=int(rng.integers(1, 4)), replace=False):
                        rows.append({
                            "order_id": oid, "customer_id": f"C{cid:05d}", "city": city,
                            "order_date": later.to_timestamp() + pd.Timedelta(days=day - 1),
                            "product": p, "qty": int(rng.integers(1, 4)), "unit_price": products[p],
                        })
                loyalty *= 0.93                                 # interest fades over time
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "plant_shop_orders.csv", index=False)
    return len(df)


# 2. Weather stations — high-frequency sensor readings (generated at query time, see project 02).
def weather_stations():
    n = 40
    df = pd.DataFrame({
        "station_id": [f"WS-{i:03d}" for i in range(n)],
        "region": rng.choice(["Highland", "Coastal", "Urban", "Valley"], n),
        "elevation_m": rng.integers(2, 1800, n),
    })
    df.to_csv(OUT / "weather_stations.csv", index=False)
    return len(df)


# 3. "Kopi Senja" — coffee chain daily sales per store and menu item.
def coffee_sales():
    stores = ["Malioboro", "Kemang", "Dago", "Tunjungan", "Sanur", "Kotabaru", "Senopati"]
    menu = {"Es Kopi Susu": 25_000, "Americano": 22_000, "Latte": 30_000, "Matcha Latte": 32_000,
            "Croissant": 28_000, "Banana Bread": 24_000}
    days = pd.date_range("2026-05-01", "2026-06-30", freq="D")
    rows = []
    for s_idx, s in enumerate(stores):
        base = 60 + s_idx * 12
        for d in days:
            weekend = 1.35 if d.dayofweek >= 5 else 1.0
            for item, price in menu.items():
                qty = rng.poisson(base * weekend * rng.uniform(0.15, 0.3))
                if s == "Dago" and d == days[-1]:
                    qty = int(qty * 0.35)                      # planted anomaly: outage
                if s == "Sanur" and d == days[-1] and item == "Matcha Latte":
                    qty = int(qty * 3.2)                       # planted anomaly: promo spike
                rows.append({"date": d.date(), "store": s, "item": item, "cups_sold": qty,
                             "revenue": qty * price})
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "coffee_daily_sales.csv", index=False)
    return len(df)


# 4. "LinguaPlus" — language school: inquiry event log (one row per funnel event).
def language_school_events():
    channels = ["Instagram Ads", "Google Search", "Referral", "Walk-in", "TikTok"]
    courses = ["English IELTS", "Japanese N5", "Korean Basic", "Mandarin HSK1", "German A1"]
    rows = []
    for i in range(1, 2401):
        lead = f"L{i:05d}"
        t = pd.Timestamp("2025-07-01") + pd.Timedelta(minutes=int(rng.integers(0, 60 * 24 * 330)))
        ch, course = rng.choice(channels), rng.choice(courses)
        rows.append((lead, t, "inquiry", ch, course))
        p_trial = {"Referral": .65, "Walk-in": .6, "Google Search": .45}.get(ch, .3)
        if rng.random() < p_trial:
            t += pd.Timedelta(days=int(rng.integers(1, 15)))
            rows.append((lead, t, "trial_class", ch, course))
            if rng.random() < .55:
                t += pd.Timedelta(days=int(rng.integers(1, 10)))
                rows.append((lead, t, "enrolled", ch, course))
                if rng.random() < .25:
                    t += pd.Timedelta(days=int(rng.integers(30, 120)))
                    rows.append((lead, t, "dropped_out", ch, course))
        elif rng.random() < .4:
            t += pd.Timedelta(days=int(rng.integers(2, 20)))
            rows.append((lead, t, "no_response", ch, course))
    df = pd.DataFrame(rows, columns=["lead_id", "event_time", "event", "channel", "course"])
    df.to_csv(OUT / "language_school_events.csv", index=False)
    return len(df)


# 5. Hotel guest reviews with a hand-labelled topic (for evaluating the classifier).
def hotel_reviews():
    templates = {
        "cleanliness": ["The room was {a} clean and the sheets smelled fresh",
                        "Found dust under the bed and the bathroom was {b}",
                        "Housekeeping did a {a} job, spotless towels"],
        "staff": ["Front desk staff were {a} friendly and helpful",
                  "The receptionist was {b} rude when we checked in",
                  "Concierge gave {a} tips for local food"],
        "food": ["Breakfast buffet was {a} with many local dishes",
                 "The nasi goreng at the restaurant tasted {b}",
                 "Room service dinner arrived cold and {b}"],
        "location": ["Walking distance to the beach, {a} location",
                     "Far from the city center, taxi was {b}",
                     "Close to the train station, {a} for business trips"],
        "price": ["Great value for money, {a} deal",
                  "Too expensive for what you get, {b}",
                  "Hidden fees at checkout were {b}"],
    }
    good = ["very", "really", "super", "amazing", "great"]
    bad = ["dirty", "awful", "disappointing", "terrible", "bland"]
    # Realistic noise: reviews that mention a second topic in passing, and vague
    # reviews with no obvious keyword (a human still labelled them).
    vague = {"cleanliness": "Honestly the bathroom smelled weird the whole stay",
             "staff": "Nobody answered the phone when we called downstairs",
             "food": "Morning meal options were limited after 9am",
             "location": "Getting here at night was a hassle",
             "price": "Not sure it was worth what we paid"}
    rows = []
    for i in range(600):
        topic = rng.choice(list(templates))
        text = rng.choice(templates[topic]).format(a=rng.choice(good), b=rng.choice(bad))
        r = rng.random()
        if r < 0.18:
            other = rng.choice([t for t in templates if t != topic])
            text += ". " + rng.choice(templates[other]).format(a=rng.choice(good), b=rng.choice(bad)).split(",")[0].lower()
        elif r < 0.26:
            text = vague[topic]
        rows.append({"review_id": f"R{i:04d}", "stars": int(rng.integers(1, 6)), "text": text, "label": topic})
    pd.DataFrame(rows).to_csv(OUT / "hotel_reviews.csv", index=False)
    return len(rows)


# 6. "Ruang Kerja" — coworking space memberships, exported from two branch systems
#    that never agreed on formats. Deliberately messy.
def coworking_memberships():
    companies = ["Arunika Studio", "Batik Digital", "Cakra Logistik", "Dewata Travel", "Elang Fintech",
                 "Flora Kids", "Garuda Robotics", "Harmoni Events", "Indigo Labs", "Jati Furniture",
                 "Kirana Foods", "Lintas Media", "Mega Arsitek", "Nusa Games", "Ombak Surf Co",
                 "Pelita Edu", "Rimba Coffee", "Samudra Legal", "Tirta Wellness", "Umbra Design",
                 "Vokal Podcast", "Wira Consulting", "Yasa Health", "Zamrud Craft"]
    plans = {"Hot Desk": 1_500_000, "Dedicated Desk": 2_750_000, "Private Office": 9_000_000}

    def messy_name(n):
        return rng.choice([n, n.upper(), n.lower(), f"PT {n}", f"{n} ", n.replace(" ", "  ")])

    rows = []
    months = pd.period_range("2025-07", "2026-06", freq="M")
    for c in companies:
        plan = rng.choice(list(plans), p=[.5, .35, .15])
        branch = rng.choice(["Jakarta", "Bali"])
        seats = int(rng.integers(1, 8)) if plan != "Private Office" else 1
        start = int(rng.integers(0, 6))
        paying = True
        for m in months[start:]:
            if paying and rng.random() < 0.12:
                paying = False                     # churn
            elif not paying and rng.random() < 0.25:
                paying = True                      # reactivation
            if not paying:
                continue
            day = int(rng.integers(1, 28))
            amount = plans[plan] * seats
            if branch == "Jakarta":
                rows.append({"source": "jakarta_pos", "company": messy_name(c), "plan": plan,
                             "paid_on": f"{day:02d}/{m.month:02d}/{m.year}", "amount": f"Rp {amount:,.0f}".replace(",", "."),
                             "seats": seats})
            else:
                rows.append({"source": "bali_sheet", "company": messy_name(c), "plan": plan.lower(),
                             "paid_on": f"{m.year}-{m.month:02d}-{day:02d}", "amount": f"{amount / 16_000:.2f} USD",
                             "seats": seats})
            if rng.random() < 0.06:                # duplicate export row
                rows.append(dict(rows[-1]))
    df = pd.DataFrame(rows).sample(frac=1, random_state=1)
    df.to_csv(OUT / "coworking_payments_raw.csv", index=False)
    pd.DataFrame({"account_manager": ["Ayu", "Bima", "Citra"], "branch": ["Jakarta", "Jakarta", "Bali"],
                  "max_accounts": [9, 9, 10]}).to_csv(OUT / "account_managers.csv", index=False)
    return len(df)


if __name__ == "__main__":
    for fn in [plant_shop_orders, weather_stations, coffee_sales, language_school_events, hotel_reviews,
               coworking_memberships]:
        print(f"{fn.__name__:24s} {fn():>8,} rows")
