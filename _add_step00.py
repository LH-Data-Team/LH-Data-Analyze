import json, os, sys
sys.stdout.reconfigure(encoding='utf-8')

NB_PATH = r'c:\Users\chyr0\Desktop\LH\LH-Data-Analyze\epdo_analysis\scripts\통합분석.ipynb'

with open(NB_PATH, encoding='utf-8') as f:
    nb = json.load(f)

# ── STEP 00 코드 ─────────────────────────────────────────────────────────────
STEP00_CODE = r'''import geopandas as gpd
import pandas as pd
import numpy as np
import os, csv, warnings
from collections import defaultdict, Counter

warnings.filterwarnings("ignore")
CRS_GEO  = "EPSG:4326"
CRS_PROJ = "EPSG:5186"
DATA_DIR  = os.path.join(BASE_DIR, "data")

def find_col(df, *kws):
    cl = {c.lower().replace(" ","").replace("_",""): c for c in df.columns}
    for kw in kws:
        kw2 = kw.lower().replace(" ","").replace("_","")
        for k, v in cl.items():
            if kw2 in k: return v
    return None

def to_gdf(csv_path):
    df = pd.read_csv(csv_path, encoding="utf-8-sig", low_memory=False)
    lat = find_col(df, "위도","lat","latitude","ycoord","y좌표")
    lon = find_col(df, "경도","lon","longitude","xcoord","x좌표")
    if not lat or not lon:
        print(f"  좌표 탐지 실패: {os.path.basename(csv_path)}  컬럼: {list(df.columns[:8])}")
        return None
    df[lat] = pd.to_numeric(df[lat], errors="coerce")
    df[lon] = pd.to_numeric(df[lon], errors="coerce")
    df = df.dropna(subset=[lat, lon])
    src = CRS_PROJ if df[lat].median() > 1000 else CRS_GEO
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon], df[lat]), crs=src)
    return gdf.to_crs(CRS_PROJ)

print("=" * 60)
print("STEP 00 - 원시 데이터 전처리")
print("=" * 60)

# 1. 기본 데이터 로드
print("\n[1] 격자 / 도로망 / 사고 데이터 로드...")
grids = gpd.read_file(os.path.join(DATA_DIR, "01._격자_(4개_시·구).geojson")).to_crs(CRS_PROJ)
gc = find_col(grids, "gid") or grids.columns[0]
grids = grids.rename(columns={gc: "gid"})
print(f"    격자: {len(grids)}개")

roads = gpd.read_file(os.path.join(DATA_DIR, "08.상세도로망_네트워크.geojson")).to_crs(CRS_PROJ)
print(f"    링크: {len(roads)}개  컬럼: {[c for c in roads.columns if c != 'geometry']}")

acc_raw = gpd.read_file(os.path.join(DATA_DIR, "13._교통사고이력.geojson"))
print(f"    사고: {len(acc_raw)}건  컬럼: {[c for c in acc_raw.columns if c != 'geometry']}")
acc = acc_raw.to_crs(CRS_PROJ)

uid_c  = find_col(acc, "uid","번호","사고번호") or acc.columns[0]
svr_c  = find_col(acc, "사상자","svrity","injury","피해구분","중증도","severity")
yr_c   = find_col(acc, "발생년","년도","acc_yr","year")
mon_c  = find_col(acc, "발생월","acc_mon","month")
time_c = find_col(acc, "발생시","시각","acc_time","hour","time")
week_c = find_col(acc, "요일","week")
type_c = find_col(acc, "사고유형","acc_type","type")
viol_c = find_col(acc, "법규위반","violation","viol")
print(f"    매핑: uid={uid_c}, 심각도={svr_c}, 년={yr_c}, 월={mon_c}, 요일={week_c}")

SVRITY_KEYS = ["사망","중상","경상","부상신고","상해없음","기타불명"]
WEEKEND = {"토","토요일","일","일요일","sat","sun","saturday","sunday"}

def norm_svr(v):
    v = str(v).strip()
    for k in SVRITY_KEYS:
        if k in v: return k
    return v

def norm_week(v):
    return "주말" if str(v).strip().lower() in WEEKEND else "평일"

# 2. 교통사고 → 링크 매핑
print("\n[2] 교통사고 → 링크 매핑 (sjoin_nearest)...")
acc_r = acc.reset_index(drop=True)
road_keep = [c for c in ["link_id","road_name","road_rank","geometry"] if c in roads.columns or c == "geometry"]
mapped = gpd.sjoin_nearest(acc_r, roads[road_keep].reset_index(drop=True), how="left", distance_col="_d")
mapped["_lon"] = acc_raw.reset_index(drop=True).geometry.x
mapped["_lat"] = acc_raw.reset_index(drop=True).geometry.y

def gv(row, col, default=""):
    return row[col] if col and col in row.index and pd.notna(row[col]) else default

out_link = []
for _, r in mapped.iterrows():
    out_link.append({
        "uid":           gv(r, uid_c),
        "link_id":       gv(r, "link_id"),
        "road_name":     gv(r, "road_name"),
        "injury_svrity": norm_svr(gv(r, svr_c)) if svr_c else "",
        "epdo_score":    0,
        "acc_yr":        gv(r, yr_c),
        "acc_mon":       gv(r, mon_c),
        "acc_time":      gv(r, time_c),
        "week_type":     norm_week(gv(r, week_c)) if week_c else "평일",
        "acc_type":      gv(r, type_c),
        "violation":     gv(r, viol_c),
        "road_type":     gv(r, "road_rank"),
        "lon":           r["_lon"],
        "lat":           r["_lat"],
    })

OUT_LINK = os.path.join(OUTPUT_DIR, "00_교통사고_링크매핑.csv")
with open(OUT_LINK, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out_link[0].keys()))
    w.writeheader(); w.writerows(out_link)
print(f"    저장: {OUT_LINK} ({len(out_link):,}건)")
print(f"    심각도: {dict(Counter(r['injury_svrity'] for r in out_link).most_common(6))}")

# 3. 교통사고 → 격자 매핑
print("\n[3] 교통사고 → 격자 매핑...")
ag = gpd.sjoin(acc_r, grids[["gid","geometry"]], how="left", predicate="within")
acc_out = acc_raw.copy()
acc_out["grid_gid"] = ag["gid"].values
if svr_c:
    acc_out["injury_svrity"] = acc_out[svr_c].apply(norm_svr)
elif "injury_svrity" not in acc_out.columns:
    acc_out["injury_svrity"] = ""
OUT_GJ = os.path.join(OUTPUT_DIR, "00_교통사고_격자매핑.geojson")
acc_out.to_file(OUT_GJ, driver="GeoJSON")
print(f"    저장: {OUT_GJ}")

# 4. 격자별 인프라 통합
print("\n[4] 격자별 인프라 통합...")
res = pd.DataFrame({"grid_gid": grids["gid"].values})

FACILS = [
    ("18._횡단보도_위치정보.csv",  "crosswalk_cnt"),
    ("14._어린이보호구역.csv",      "child_zone_cnt"),
    ("15._학교현황.csv",            "school_cnt"),
    ("16._유치원현황.csv",          "kindergarten_cnt"),
    ("17._어린이집현황.csv",        "daycare_cnt"),
    ("19._버스정류장_위치정보.csv", "bus_stop_cnt"),
    ("20._CCTV_현황.csv",           "cctv_cnt"),
]
for fname, col in FACILS:
    fp = os.path.join(DATA_DIR, fname)
    if not os.path.exists(fp):
        res[col] = 0; print(f"  없음: {fname}"); continue
    gdf = to_gdf(fp)
    if gdf is None:
        res[col] = 0; continue
    j = gpd.sjoin(gdf, grids[["gid","geometry"]], how="left", predicate="within")
    agg = j.groupby("gid").size().reset_index().rename(columns={"gid":"grid_gid", 0: col})
    res = res.merge(agg, on="grid_gid", how="left")
    res[col] = res[col].fillna(0).astype(int)
    print(f"  {fname}: {res[col].sum():.0f}개")

# CCTV 대수
fp = os.path.join(DATA_DIR, "20._CCTV_현황.csv")
if os.path.exists(fp):
    df_cc = pd.read_csv(fp, encoding="utf-8-sig", low_memory=False)
    cam_c = find_col(df_cc, "대수","카메라","설치대수","cam")
    gdf_cc = to_gdf(fp)
    if gdf_cc is not None and cam_c:
        gdf_cc[cam_c] = pd.to_numeric(gdf_cc[cam_c], errors="coerce").fillna(1)
        j = gpd.sjoin(gdf_cc[["geometry", cam_c]], grids[["gid","geometry"]], how="left", predicate="within")
        agg = j.groupby("gid")[cam_c].sum().reset_index().rename(columns={"gid":"grid_gid", cam_c:"cctv_cam_cnt"})
        res = res.merge(agg, on="grid_gid", how="left")
    else:
        res["cctv_cam_cnt"] = res["cctv_cnt"]
else:
    res["cctv_cam_cnt"] = res["cctv_cnt"]
res["cctv_cam_cnt"] = res["cctv_cam_cnt"].fillna(0).astype(int)

# 유치원 원아수
fp = os.path.join(DATA_DIR, "16._유치원현황.csv")
if os.path.exists(fp):
    df_kg = pd.read_csv(fp, encoding="utf-8-sig", low_memory=False)
    cc = find_col(df_kg, "원아수","학생수","아동수","정원","child","student")
    gdf_kg = to_gdf(fp)
    if gdf_kg is not None and cc:
        gdf_kg[cc] = pd.to_numeric(gdf_kg[cc], errors="coerce").fillna(0)
        j = gpd.sjoin(gdf_kg[["geometry", cc]], grids[["gid","geometry"]], how="left", predicate="within")
        agg = j.groupby("gid")[cc].sum().reset_index().rename(columns={"gid":"grid_gid", cc:"kindergarten_child_cnt"})
        res = res.merge(agg, on="grid_gid", how="left")
    else:
        res["kindergarten_child_cnt"] = res["kindergarten_cnt"]
else:
    res["kindergarten_child_cnt"] = res["kindergarten_cnt"]
res["kindergarten_child_cnt"] = res["kindergarten_child_cnt"].fillna(0).astype(int)

# 과속방지턱 (이미 격자 매핑됨)
fp = os.path.join(DATA_DIR, "21.1_과속방지턱_격자매핑.csv")
if os.path.exists(fp):
    df_sb = pd.read_csv(fp, encoding="utf-8-sig", low_memory=False)
    print(f"  과속방지턱 컬럼: {list(df_sb.columns)}")
    gc2 = find_col(df_sb, "gid","grid","격자") or df_sb.columns[0]
    cn  = find_col(df_sb, "cnt","count","개수")
    lc  = find_col(df_sb, "below","미만","저","low")
    hc  = find_col(df_sb, "above","이상","고","high")
    sb  = df_sb.rename(columns={gc2: "grid_gid"})
    sb["speedbump_cnt"]        = pd.to_numeric(sb[cn]  if cn else 1, errors="coerce").fillna(0)
    sb["speedbump_hght_below"] = pd.to_numeric(sb[lc]  if lc else 0, errors="coerce").fillna(0)
    sb["speedbump_hght_above"] = pd.to_numeric(sb[hc]  if hc else 0, errors="coerce").fillna(0)
    sb_agg = sb.groupby("grid_gid")[["speedbump_cnt","speedbump_hght_below","speedbump_hght_above"]].sum().reset_index()
    res = res.merge(sb_agg, on="grid_gid", how="left")
else:
    res["speedbump_cnt"] = res["speedbump_hght_below"] = res["speedbump_hght_above"] = 0
for c in ["speedbump_cnt","speedbump_hght_below","speedbump_hght_above"]:
    res[c] = res[c].fillna(0).astype(int)

OUT_INFRA = os.path.join(OUTPUT_DIR, "00_격자별_통합데이터.csv")
res.to_csv(OUT_INFRA, index=False, encoding="utf-8-sig")
print(f"\n    저장: {OUT_INFRA}  ({len(res):,}개 격자)")

# 5. 링크별 사고 집계
print("\n[5] 링크별 사고 집계...")
link_agg = defaultdict(list)
for r in out_link:
    lid = str(r.get("link_id",""))
    if lid and lid not in ("","nan"):
        link_agg[lid].append(str(r.get("uid","")))

OUT_AGG = os.path.join(OUTPUT_DIR, "00_링크별_사고집계.csv")
with open(OUT_AGG, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["link_id","accident_cnt","accident_uids"])
    for lid, uids in link_agg.items():
        w.writerow([lid, len(uids), "|".join(uids)])
print(f"    저장: {OUT_AGG} ({len(link_agg):,}개 링크)")

print("\n" + "="*60)
print("STEP 00 완료")
print("="*60)
'''

def mdc(src, cid):
    return {"cell_type":"markdown","id":cid,"metadata":{},"source":src.splitlines(keepends=True)}

def mcc(src, cid):
    return {"cell_type":"code","execution_count":None,"id":cid,"metadata":{},"outputs":[],"source":src.splitlines(keepends=True)}

# STEP 00 셀 삽입 (index 2 앞)
new_cells = [
    mdc("---\n\n## STEP 00 - 전처리 (원시 데이터 → 분석용 파일 생성)\n\n원시 COMPAS 데이터로부터 STEP 01~11에 필요한 중간 파일을 생성합니다.", "step00-md"),
    mcc(STEP00_CODE, "step00-code"),
]
nb["cells"] = nb["cells"][:2] + new_cells + nb["cells"][2:]
print(f"STEP 00 삽입 완료. 총 셀: {len(nb['cells'])}")

# 하위 STEP 경로 업데이트
REPLACEMENTS = [
    ('os.path.join(BASE_DIR, "data", "13._교통사고_링크매핑.csv")',
     'os.path.join(EPDO_DIR, "epdo_analysis", "output", "00_교통사고_링크매핑.csv")'),
    ("os.path.join(BASE_DIR, 'data', '13._교통사고_링크매핑.csv')",
     "os.path.join(EPDO_DIR, 'epdo_analysis', 'output', '00_교통사고_링크매핑.csv')"),
    ('os.path.join(BASE_DIR, "data", "13._링크별_사고집계.csv")',
     'os.path.join(EPDO_DIR, "epdo_analysis", "output", "00_링크별_사고집계.csv")'),
    ('os.path.join(BASE_DIR, "data", "13._교통사고_격자매핑.geojson")',
     'os.path.join(EPDO_DIR, "epdo_analysis", "output", "00_교통사고_격자매핑.geojson")'),
    ('os.path.join(BASE_DIR, "data", "격자별_통합데이터.csv")',
     'os.path.join(EPDO_DIR, "epdo_analysis", "output", "00_격자별_통합데이터.csv")'),
    ("os.path.join(BASE_DIR, 'data', '격자별_통합데이터.csv')",
     "os.path.join(EPDO_DIR, 'epdo_analysis', 'output', '00_격자별_통합데이터.csv')"),
]

changed = 0
for cell in nb["cells"]:
    if cell["cell_type"] != "code":
        continue
    src = "".join(cell["source"])
    orig = src
    for old, new in REPLACEMENTS:
        src = src.replace(old, new)
    if src != orig:
        cell["source"] = src.splitlines(keepends=True)
        changed += 1
print(f"경로 업데이트: {changed}개 셀")

with open(NB_PATH, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print("저장 완료")
