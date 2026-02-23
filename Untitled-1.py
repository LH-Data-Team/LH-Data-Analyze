# -*- coding: utf-8 -*-
"""
(19번) 버스정류장 -> gid 매핑 -> busstop_cnt 생성 -> (이미 21이 plus된) grid_master_plus21.csv에 추가(조인) -> 저장

입력
- grid_master_plus21.csv
- 01._격자_(4개_시·구).geojson
- 02._격자_(하남교산).geojson
- 19._버스정류장_위치정보.csv  (컬럼: lon, lat, bis_id)

출력
- grid_master_plus21_plus19.csv
"""

import pandas as pd
import geopandas as gpd

# 0) 21까지 붙은 grid_master 로드
grid_master = pd.read_csv("grid_master_plus21.csv")
grid_master["gid"] = grid_master["gid"].astype(str).str.replace(r"\.0$", "", regex=True)

# 1) grid_slim 생성 (gid + geometry)
grid1 = gpd.read_file("01._격자_(4개_시·구).geojson")
grid2 = gpd.read_file("02._격자_(하남교산).geojson")

grid = gpd.GeoDataFrame(
    pd.concat([grid1, grid2], ignore_index=True),
    geometry="geometry",
)
grid = grid.set_crs(epsg=4326, allow_override=True)
grid = grid[["gid", "geometry"]].copy()
grid["gid"] = grid["gid"].astype(str).str.replace(r"\.0$", "", regex=True)

grid_slim = grid[["gid", "geometry"]].copy()

# 2) 19 로드
df19 = pd.read_csv("19._버스정류장_위치정보.csv")

# 3) 좌표 숫자화 + 결측 제거
df19["lon"] = pd.to_numeric(df19["lon"], errors="coerce")
df19["lat"] = pd.to_numeric(df19["lat"], errors="coerce")
df19 = df19.dropna(subset=["lon", "lat"]).copy()

# 4) 포인트 생성
g19 = gpd.GeoDataFrame(
    df19,
    geometry=gpd.points_from_xy(df19["lon"], df19["lat"]),
    crs="EPSG:4326",
)

# 5) gid 매핑
j19 = (
    gpd.sjoin(g19, grid_slim, how="left", predicate="within")
      .drop(columns=["index_right"], errors="ignore")
)
j19 = j19.dropna(subset=["gid"]).copy()
j19["gid"] = j19["gid"].astype(str).str.replace(r"\.0$", "", regex=True)

# 6) gid별 버스정류장 개수(고유 bis_id)
z19 = (
    j19.groupby("gid", as_index=False)
       .agg(busstop_cnt=("bis_id", "nunique"))
)

# 7) grid_master_plus21에 추가(조인) + 저장
grid_master_plus21_plus19 = (
    grid_master
    .drop(columns=["busstop_cnt"], errors="ignore")
    .merge(z19, on="gid", how="left")
)

grid_master_plus21_plus19["busstop_cnt"] = (
    grid_master_plus21_plus19["busstop_cnt"].fillna(0).astype(int)
)

grid_master_plus21_plus19.to_csv(
    "grid_master_plus21_plus19.csv",
    index=False,
    encoding="utf-8-sig",
)

print("saved: grid_master_plus21_plus19.csv")
print(grid_master_plus21_plus19[["gid", "gbn", "busstop_cnt"]].head())