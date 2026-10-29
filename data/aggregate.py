"""
Shrinks the 75 MB review archive into a few small CSVs for the Vega-Lite site,
and prints a data-quality report so you can judge if the data is good enough.

Reads  : GoogleReview_data_cleaned.csv, TripAdvisor_data_cleaned.csv
Writes : out/city_summary.csv, out/restaurant_summary.csv, out/word_freq.csv
"""
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("out")
out.mkdir(exist_ok=True)

# city label in the data -> (full name, state name used in hh_income_state.csv, lat, lon)
CITIES = {
    "Ipoh":          ("Ipoh",          "Perak",             4.5975, 101.0901),
    "JB":            ("Johor Bahru",   "Johor",             1.4927, 103.7414),
    "KL":            ("Kuala Lumpur",  "W.P. Kuala Lumpur", 3.1390, 101.6869),
    "Kuching":       ("Kuching",       "Sarawak",           1.5535, 110.3593),
    "Langkawi":      ("Langkawi",      "Kedah",             6.3500, 99.8000),
    "Melaka":        ("Melaka",        "Melaka",            2.1896, 102.2501),
    "Miri":          ("Miri",          "Sarawak",           4.3995, 113.9914),
    "Penang":        ("George Town",   "Pulau Pinang",      5.4141, 100.3288),
    "Petaling Jaya": ("Petaling Jaya", "Selangor",          3.1073, 101.6067),
    "Shah Alam":     ("Shah Alam",     "Selangor",          3.0738, 101.5183),
}

# rough keyword guess of cuisine from the restaurant NAME (approximate)
CUISINE_KEYWORDS = {
    "Japanese": ["sushi", "ramen", "izakaya", "japan", "tokyo", "teppanyaki", "udon", "sashimi", "omakase"],
    "Korean": ["korea", "kbbq", "seoul", "kimchi", "bibimbap", "k-pot"],
    "Indian": ["indian", "mamak", "nasi kandar", "banana leaf", "briyani", "biryani", "tandoor", "curry",
               "naan", "tikka", "thosai", "dosa", "murtabak", "bhavan", "bhavan"],
    "Chinese": ["chinese", "dim sum", "dimsum", "bak kut", "hokkien", "canton", "szechuan", "hotpot", "steamboat",
                "kopitiam", "claypot", "chicken rice", "wantan", "wonton", "zi char", "tai tong",
                "面", "饭", "粥", "茶", "饼", "炒", "鸡", "肉骨茶", "点心", "小厨", "小廚", "海鲜"],
    "Malay": ["nasi ", "ayam", "satay", "laksa", "warung", "asam", "rendang", "kampung", "kampong", "sambal", "pecel"],
    "Thai": ["thai", "tom yum", "siam"],
    "Seafood": ["seafood", "crab", "prawn", "lobster", "fish head"],
    "Western": ["steak", "burger", "pizza", "pasta", "italian", "french", "trattoria", "pizzeria", "ristorante"],
    "Cafe & bar": ["cafe", "café", "coffee", "bistro", "bar ", " bar", "pub", "gastro", "brew", "tea house", "bakery", "dessert"],
}

STOP = set("""the a an and or of to in is it was for on with that this at as are be we i you they
but not have had so very our my me from their there were all just can will if about out one
would what which also been when more than get got us them its by do did like place food""".split())


def cuisine_guess(name: str) -> str:
    n = name.lower()
    for cuisine, words in CUISINE_KEYWORDS.items():
        if any(w in n for w in words):
            return cuisine
    return "Unknown"


def load(fname, source):
    df = pd.read_csv(src / fname)
    df["source"] = source
    df["Rating"] = pd.to_numeric(df["Rating"], errors="coerce")
    df = df.dropna(subset=["Rating"])
    return df


google = load("GoogleReview_data_cleaned.csv", "Google")
trip = load("TripAdvisor_data_cleaned.csv", "TripAdvisor")
df = pd.concat([google, trip], ignore_index=True)
df["review_len"] = df["Review"].astype(str).str.len()

# ---------- city summary (joins to state population / income later) ----------
g = df.groupby(["source", "Location"])
city = g.agg(
    n_reviews=("Rating", "size"),
    n_restaurants=("Restaurant", "nunique"),
    avg_rating=("Rating", "mean"),
    pct_5star=("Rating", lambda s: (s == 5).mean() * 100),
    pct_1_2star=("Rating", lambda s: (s <= 2).mean() * 100),
    median_review_len=("review_len", "median"),
).reset_index()
city["city"] = city["Location"].map(lambda c: CITIES.get(c, (c,))[0])
city["state"] = city["Location"].map(lambda c: CITIES.get(c, (None, None))[1])
city["lat"] = city["Location"].map(lambda c: CITIES.get(c, (0, 0, None, None))[2])
city["lon"] = city["Location"].map(lambda c: CITIES.get(c, (0, 0, None, None))[3])
city = city.round(2)
city.to_csv(out / "city_summary.csv", index=False)

# how many reviews gave 1-5 stars, per platform and city (heatmap chart)
df["stars"] = df["Rating"].round().clip(1, 5).astype(int)
dist = df.groupby(["source", "Location", "stars"]).size().reset_index(name="reviews")
dist["city"] = dist["Location"].map(lambda c: CITIES.get(c, (c,))[0])
dist = dist.rename(columns={"source": "platform"})
dist[["platform", "city", "stars", "reviews"]].to_csv(out / "rating_by_city.csv", index=False)

# ---------- restaurant summary (only restaurants with enough reviews) ----------
rest = (
    df.groupby(["source", "Location", "Restaurant"])
    .agg(n_reviews=("Rating", "size"), avg_rating=("Rating", "mean"),
         median_review_len=("review_len", "median"))
    .reset_index()
)
rest = rest[rest["n_reviews"] >= 20].copy()
rest["cuisine_guess"] = rest["Restaurant"].map(cuisine_guess)
rest = rest.round(2)
rest.to_csv(out / "restaurant_summary.csv", index=False)

# ---------- word frequencies: what do 5-star vs 1-2-star reviews talk about? ----------
rows = []
for source, sub in df.groupby("source"):
    for label, mask in (("high (4-5)", sub["Rating"] >= 4), ("low (1-2)", sub["Rating"] <= 2)):
        words = Counter()
        for text in sub.loc[mask, "Review"].astype(str).sample(frac=1, random_state=1).head(40000):
            words.update(w for w in re.findall(r"[a-z']{3,}", text.lower()) if w not in STOP)
        rows += [(source, label, w, c) for w, c in words.most_common(80)]
pd.DataFrame(rows, columns=["source", "rating_group", "word", "count"]).to_csv(out / "word_freq.csv", index=False)

# ---------- data-quality report ----------
print("\n=== DATA CHECK ===")
print(f"Reviews: {len(df):,}  | restaurants: {df['Restaurant'].nunique():,}")
print("\nCities per source:\n", city.pivot(index="Location", columns="source", values="n_reviews"))
print("\nAvg rating by city:\n", city.pivot(index="Location", columns="source", values="avg_rating"))
print(f"\nRestaurants with >=20 reviews: {len(rest):,}")
print("Cuisine-guess coverage (share NOT 'Unknown'): "
      f"{(rest['cuisine_guess'] != 'Unknown').mean():.0%}")
print(rest["cuisine_guess"].value_counts())
for f in out.iterdir():
    print(f"{f.name}: {f.stat().st_size/1024:.0f} KB")