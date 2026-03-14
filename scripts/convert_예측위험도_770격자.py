"""
08_하남교산_예측위험도.csv를 770개 격자 기준으로 재생성

COMPAS_08c 로직: 02번 격자(770개)를 기준으로, 23번 토지이용과 intersects 공간조인
→ 격자당 1행, 총 770행 출력

입력:
  - data/02._격자_(하남교산).geojson (770개 격자)
  - data/23._토지이용계획도_(하남교산).geojson
  - output/08_격자_종합위험지수.csv (blockType별 lu_avg_risk 계산용)
"""

import csv
import os
from collections import defaultdict

import geopandas as gpd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
_epdo = os.path.join(BASE_DIR, "epdo_analysis", "output")
if os.path.exists(_epdo) and os.path.exists(os.path.join(_epdo, "08_격자_종합위험지수.csv")):
    OUTPUT_DIR = _epdo

LU_HANAM = os.path.join(DATA_DIR, "23._토지이용계획도_(하남교산).geojson")
GRID_HANAM = os.path.join(DATA_DIR, "02._격자_(하남교산).geojson")
GRID_RISK_FILE = os.path.join(OUTPUT_DIR, "08_격자_종합위험지수.csv")
OUTPUT_08 = os.path.join(OUTPUT_DIR, "08_하남교산_예측위험도.csv")

CRS_PROJ = "EPSG:5186"

SCHOOL_TYPES = {"학교", "초등학교", "중학교", "고등학교", "교육시설"}
RESIDENT_TYPES = {"아파트", "연립주택", "다세대주택", "단독주택", "공동주택", "주상복합", "연립"}
COMMERCIAL_TYPES = {"상업", "일반상업", "근린상업", "근린생활시설용지", "상업시설"}


def main():
    # 1. 4개 신도시 blockType(land_use)별 평균 entropy_composite_risk
    lu_risk = defaultdict(list)
    with open(GRID_RISK_FILE, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            land_use = (row.get("land_use") or "").strip()
            ecr = row.get("entropy_composite_risk")
            if land_use and land_use != "미분류" and ecr:
                try:
                    lu_risk[land_use].append(float(ecr))
                except ValueError:
                    pass

    lu_avg_risk = {lt: round(sum(v) / len(v), 2) for lt, v in lu_risk.items()}
    all_risks = [r for vals in lu_risk.values() for r in vals]
    overall_avg = round(sum(all_risks) / len(all_risks), 2) if all_risks else 0.0

    lu_vals = sorted(lu_avg_risk.values())
    def _pct(vals, p):
        if not vals:
            return overall_avg
        idx = (p / 100) * (len(vals) - 1)
        lo, hi = int(idx), min(int(idx) + 1, len(vals) - 1)
        return vals[lo] + (idx - lo) * (vals[hi] - vals[lo])
    grade_high = _pct(lu_vals, 75)
    grade_mid = _pct(lu_vals, 25)

    # 2. 하남교산 격자(02) 770개 로드
    grid_gdf = gpd.read_file(GRID_HANAM).to_crs(CRS_PROJ)
    gid_col = next(
        (c for c in grid_gdf.columns if c.lower() in ("gid", "grid_gid", "grid_id")),
        grid_gdf.columns[0],
    )
    grid_gdf = grid_gdf.rename(columns={gid_col: "gid"})
    grid_gdf = grid_gdf[["gid", "geometry"]]

    # 3. 토지이용(23) 로드
    lu_gdf = gpd.read_file(LU_HANAM).to_crs(CRS_PROJ)
    lu_gdf = lu_gdf[["blockType", "geometry"]]

    # 4. 공간 조인: 격자(LEFT) x 토지이용 → 격자당 1개 blockType (keep="first")
    joined = gpd.sjoin(
        grid_gdf,
        lu_gdf,
        how="left",
        predicate="intersects",
    )
    joined = joined.drop_duplicates(subset="gid", keep="first")
    joined["blockType"] = joined["blockType"].fillna("미분류").astype(str).str.strip()
    joined = joined.drop(columns=["index_right"], errors="ignore")

    # 5. 격자별 pred_risk, risk_grade 산출
    result = []
    for _, row in joined.iterrows():
        btype = row["blockType"]
        if btype in lu_avg_risk:
            pred_risk, basis = lu_avg_risk[btype], "동일유형"
        elif btype in SCHOOL_TYPES:
            matched = [lu_avg_risk[k] for k in SCHOOL_TYPES if k in lu_avg_risk]
            pred_risk = round(sum(matched) / len(matched), 2) if matched else overall_avg
            basis = "학교유형평균"
        elif btype in RESIDENT_TYPES:
            matched = [lu_avg_risk[k] for k in RESIDENT_TYPES if k in lu_avg_risk]
            pred_risk = round(sum(matched) / len(matched), 2) if matched else overall_avg
            basis = "주거유형평균"
        elif btype in COMMERCIAL_TYPES:
            matched = [lu_avg_risk[k] for k in COMMERCIAL_TYPES if k in lu_avg_risk]
            pred_risk = round(sum(matched) / len(matched), 2) if matched else overall_avg
            basis = "상업유형평균"
        else:
            pred_risk, basis = overall_avg, "전체평균"

        risk_grade = "고위험" if pred_risk >= grade_high else ("중위험" if pred_risk >= grade_mid else "저위험")
        result.append({
            "grid_gid": row["gid"],
            "blockType": btype,
            "pred_risk": pred_risk,
            "risk_grade": risk_grade,
            "basis": basis,
        })

    result.sort(key=lambda x: -x["pred_risk"])

    # 6. 저장
    cols = ["grid_gid", "blockType", "pred_risk", "risk_grade", "basis"]
    with open(OUTPUT_08, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(result)

    n = len(result)
    high = sum(1 for r in result if r["risk_grade"] == "고위험")
    mid = sum(1 for r in result if r["risk_grade"] == "중위험")
    low = sum(1 for r in result if r["risk_grade"] == "저위험")
    print(f"저장: {OUTPUT_08}")
    print(f"  격자 수: {n}개 (770개 목표)")
    print(f"  고위험: {high} | 중위험: {mid} | 저위험: {low}")


if __name__ == "__main__":
    main()
