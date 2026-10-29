"""Yearly city ranking from TripAdvisor review dates (Google has no dates).
Output: data/out/city_year_rank.csv  (Location, year, n_reviews, avg_rating, rank)
"""
import sys, pandas as pd

SRC = sys.argv[1] if len(sys.argv) > 1 else "data/Reviews/TripAdvisor_data_cleaned.csv"
YEARS = range(2015, 2021)   # 2015-2020: enough reviews in every year
MIN_REVIEWS = 50            # skip city-years with fewer reviews than this

d = pd.read_csv(SRC, usecols=["Rating", "Location", "Dates"])
# Dates look like "Reviewed 12 December 2019"; a few relative ones ("5 days ago") are dropped
d["year"] = pd.to_numeric(d.Dates.str.extract(r"(\d{4})\s*$")[0], errors="coerce")
d = d[d.year.isin(YEARS)]

t = (d.groupby(["Location", "year"]).Rating
       .agg(n_reviews="size", avg_rating="mean").reset_index())
t = t[t.n_reviews >= MIN_REVIEWS].copy()
t["avg_rating"] = t.avg_rating.round(2)
t["year"] = t.year.astype(int)
t["rank"] = t.groupby("year").avg_rating.rank(ascending=False, method="min").astype(int)
t.sort_values(["year", "rank"]).to_csv("data/out/city_year_rank.csv", index=False)
print(len(t), "rows written")