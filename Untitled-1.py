import pandas as pd
import geopandas as gpd
import numpy as np

BASE_DIR = r"C:\Users\eskao\OneDrive\바탕 화면\LH-Data-Analyze"

BASE_FILE = BASE_DIR + r"\1+18+19+20+21.csv"
GRID_FILE = BASE_DIR + r"\01._격자_(4개_시·구).geojson"
ACC13_FILE = BASE_DIR + r"\13._교통사고이력.geojson"

OUT_FILE = BASE_DIR + r"\1+13+18+19+20+21.csv"

# 0) 베이스 로드 (gid 있어야 함)
base = pd.read_csv(BASE_FILE)
base["gid"] = base["gid"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
base = base.drop_duplicates(subset=["gid"]).copy()

# 1) 격자 로드
grid = gpd.read_file(GRID_FILE)[["gid", "geometry"]].copy()
grid["gid"] = grid["gid"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()

# 2) 13 사고 로드 (포인트라고 가정)
acc13 = gpd.read_file(ACC13_FILE)
# CRS 맞추기
if acc13.crs is None:
    acc13 = acc13.set_crs(grid.crs, allow_override=True)
elif grid.crs is not None and acc13.crs != grid.crs:
    acc13 = acc13.to_crs(grid.crs)

# 3) 공간조인으로 gid 붙이기
j13 = gpd.sjoin(acc13, grid, how="left", predicate="within").drop(columns=["index_right"], errors="ignore")
j13 = j13.dropna(subset=["gid"]).copy()
j13["gid"] = j13["gid"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()

# 4) 네가 지정한 4개 컬럼만 "격자 내 합계"
sum_cols = ["dprs_cnt", "sep_cnt", "slp_cnt", "inj_aplcnt_cnt"]
for c in sum_cols:
    if c in j13.columns:
        j13[c] = pd.to_numeric(j13[c], errors="coerce").fillna(0)
    else:
        j13[c] = 0

z13_4 = j13.groupby("gid", as_index=False)[sum_cols].sum()

# 5) (검색용) 13번의 나머지 컬럼들도 gid별로 한 번에 집계해 둠
# - 숫자형은 sum, 그 외는 mode(최빈값)로 1개만
def mode1(s):
    s = s.dropna()
    if len(s) == 0:
        return pd.NA
    return s.mode().iloc[0]

agg_map = {}
for c in j13.columns:
    if c in ["geometry", "gid"]:
        continue
    if pd.api.types.is_numeric_dtype(j13[c]):
        agg_map[c] = "sum"
    else:
        agg_map[c] = mode1

z13_all = j13.groupby("gid", as_index=False).agg(agg_map)

def search_gid_13(gid: str):
    """gid 넣으면 13번 집계값(전체 컬럼) 한 줄 반환"""
    gid = str(gid).replace(".0", "").strip()
    row = z13_all.loc[z13_all["gid"] == gid]
    if row.empty:
        print("해당 gid 없음:", gid)
        return None
    d = row.iloc[0].to_dict()
    # 보기 좋게 출력
    for k, v in d.items():
        print(f"{k}: {v}")
    return d

# 6) 베이스에 13(4개)만 붙이고 저장 (geometry 없이)
out = base.drop(columns=sum_cols, errors="ignore").merge(z13_4, on="gid", how="left")
for c in sum_cols:
    out[c] = out[c].fillna(0).astype(int)

out.to_csv(OUT_FILE, index=False, encoding="utf-8-sig")
print("saved:", OUT_FILE, "rows:", len(out))

# ---- 사용 예시(검색 기능) ----
# search_gid_13("12345")