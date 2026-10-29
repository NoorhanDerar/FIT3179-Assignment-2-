"""Make circle positions for a Dorling cartogram of Malaysian states.
Circle area is proportional to population; circles start at each state's
centre and are pushed apart until they stop overlapping.
Output: data/out/state_dorling.csv
"""
import sys, json, math
import numpy as np, pandas as pd

GEO = sys.argv[1] if len(sys.argv) > 1 else "data/geoBoundaries-MYS-ADM1_simplified.geojson"
CTX = sys.argv[2] if len(sys.argv) > 2 else "data/out/state_context.csv"
# States that have restaurant reviews in the dataset (derived from the 10 cities)
REVIEW_STATES = {"Kuala Lumpur", "Selangor", "Johor", "Penang", "Perak",
                 "Malacca", "Sarawak", "Kedah"}      # names as in the GeoJSON

PX_PER_DEG = 55     # map scale before pushing circles apart
R_MAX = 44          # radius (px) of the biggest circle (Selangor)
GAP = 2             # minimum gap between circles (px)

def ring_centroid(r):
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(r, r[1:]):
        c = x0 * y1 - x1 * y0
        a += c; cx += (x0 + x1) * c; cy += (y0 + y1) * c
    a /= 2
    return (cx / (6 * a), cy / (6 * a), abs(a)) if a else (r[0][0], r[0][1], 0)

def centroid(geom):
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    tot = sx = sy = 0.0
    for p in polys:
        x, y, a = ring_centroid(p[0])          # outer ring only
        tot += a; sx += x * a; sy += y * a
    return sx / tot, sy / tot

g = json.load(open(GEO))
rows = []
for f in g["features"]:
    lon, lat = centroid(f["geometry"])
    rows.append({"state_geo": f["properties"]["shapeName"], "lon": lon, "lat": lat})
d = pd.DataFrame(rows).merge(pd.read_csv(CTX), on="state_geo")

# Shorten the sea gap between Peninsular Malaysia and Borneo to save space
east = d.lon > 108
gap = d.lon[east].min() - d.lon[~east].max()
d.loc[east, "lon"] -= (gap - 1.0)

d["r"] = R_MAX * np.sqrt(d.population_2026_thousands / d.population_2026_thousands.max())
d["x0"] = (d.lon - d.lon.min()) * PX_PER_DEG
d["y0"] = (d.lat.max() - d.lat) * PX_PER_DEG
pos = d[["x0", "y0"]].to_numpy().copy()
home = pos.copy()
r = d.r.to_numpy()

for _ in range(2000):                      # push overlapping circles apart
    moved = False
    for i in range(len(d)):
        for j in range(i + 1, len(d)):
            v = pos[j] - pos[i]
            dist = math.hypot(*v) or 1e-6
            need = r[i] + r[j] + GAP
            if dist < need:
                push = (need - dist) / 2 * v / dist
                pos[i] -= push; pos[j] += push; moved = True
    pos += 0.02 * (home - pos)             # gentle pull back towards true location
    if not moved:
        break

pos -= pos.min(axis=0) - R_MAX * 0.2       # shift so everything is inside the canvas
pad = d.r.max() + 6
pos[:, 0] += pad - (pos[:, 0] - r).min()
pos[:, 1] += pad - (pos[:, 1] - r).min()
d["x"], d["y"] = pos[:, 0].round(1), pos[:, 1].round(1)
d["r"] = d.r.round(1)
d["has_reviews"] = np.where(d.state_geo.isin(REVIEW_STATES), "Yes", "No")
# Labels: inside big circles, above small ones; a few hand-placed to avoid clashes
small = d.population_2026_thousands < 1500
d["label"] = d.state_geo.replace({"Kuala Lumpur": "KL", "Malacca": "Melaka", "Negeri Sembilan": "N. Sembilan"})
d["label_pos"] = np.where(small, "above", "inside")
d["label_x"] = d.x
d["label_y"] = np.where(small, d.y - d.r - 7, d.y)
# Hand-placed labels for the crowded middle of the Peninsula
m = d.state_geo == "Malacca"                      # fits inside its circle
d.loc[m, "label_pos"] = "inside"
d.loc[m, "label_y"] = d.y
ns = d.state_geo == "Negeri Sembilan"             # to the right of its circle
d.loc[ns, "label_pos"] = "right"
d.loc[ns, "label_x"] = d.x + d.r + 4
d.loc[ns, "label_y"] = d.y
pj = d.state_geo == "Putrajaya"                   # tiny circle: label just below
d.loc[pj, "label_pos"] = "below"
d.loc[pj, "label_x"] = d.x - 8
d.loc[pj, "label_y"] = d.y + 36
d["label_x"] = d.label_x.round(1); d["label_y"] = d.label_y.round(1)
d["label_color"] = np.where((d.label_pos == "inside") & (d.income_median_2024 >= 7000), "white", "#2B2118")
out = d[["state_geo", "state_dosm", "population_2026_thousands", "income_median_2024",
         "has_reviews", "x", "y", "r", "label", "label_pos", "label_x", "label_y", "label_color"]]
out.to_csv("data/out/state_dorling.csv", index=False)
print(out.to_string(index=False)); print("canvas needs about", int((pos[:,0]+r).max()+pad), "x", int((pos[:,1]+r).max()+pad))