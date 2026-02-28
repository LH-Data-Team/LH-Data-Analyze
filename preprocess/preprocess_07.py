# -*- coding: utf-8 -*-
"""07._주중주말_서비스인구 전처리"""

import pandas as pd
import geopandas as gpd
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
RAW_PATH = os.path.join(PROJECT_DIR, "07._주중주말_서비스인구.csv")
GRID_PATH = os.path.join(PROJECT_DIR, "01._격자_(4개_시·구).geojson")
OUT_PATH = os.path.join(SCRIPT_DIR, "07._주중주말_서비스인구_preprocessed.csv")

df = pd.read_csv(RAW_PATH, encoding="utf-8-sig")

pop_cols = ["w_pop", "v_pop"]
df = df[["hw"] + pop_cols + ["lon", "lat"]].copy()

df[pop_cols] = df[pop_cols].fillna(0)
df = df.dropna(subset=["lon", "lat"]).reset_index(drop=True)
df[pop_cols] = df[pop_cols].clip(lower=0)

# 좌표(lon/lat)가 속한 격자의 gid를 공간조인으로 매핑
points_gdf = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df["lon"], df["lat"]),
    crs="EPSG:4326",
)
grid_gdf = gpd.read_file(GRID_PATH)[["gid", "geometry"]].to_crs(points_gdf.crs)
joined = gpd.sjoin(points_gdf, grid_gdf, how="left", predicate="within")
df = pd.DataFrame(joined.drop(columns=["geometry", "index_right"], errors="ignore"))

outlier_info = []
for c in pop_cols:
    nonzero = df.loc[df[c] > 0, c]
    if len(nonzero) == 0:
        continue
    q1, q3 = nonzero.quantile(0.25), nonzero.quantile(0.75)
    upper = q3 + 1.5 * (q3 - q1)
    if (nonzero > upper).sum() > 0:
        outlier_info.append({"col": c, "upper": upper})

if outlier_info:
    df["outlier_flag"] = False
    for info in outlier_info:
        df.loc[df[info["col"]] > info["upper"], "outlier_flag"] = True

df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
