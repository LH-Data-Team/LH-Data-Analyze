"""
08_하남교산_격자별_ECR_최종.csv 생성 스크립트
- 사고/EPDO: 13번 교통사고이력 + 02번 하남교산 격자 point-in-polygon
- 7개 인자: 08_격자_종합위험지수 (하남 격자만)
- ECR(위험지수): entropy_composite_risk = EPDO × (1 + correction_index)
- correction_index: 09_엔트로피_가중치 기반, 41격자 min-max 정규화
"""

import os
import csv
import geopandas as gpd
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

EPDO_WEIGHTS = {"사망": 391, "중상": 69, "경상": 8, "부상신고": 6, "상해없음": 1, "기타불명": 8}
FACTOR_COLS = ["elderly_res_ratio", "vuln_peak_pop", "grid_congestion", "grid_avg_speed", "weekend_ratio", "gap_cnt", "vuln_float_ratio"]
SAFETY_COLS = ["crosswalk_cnt", "child_zone_cnt", "speedbump_cnt", "cctv_cnt", "cctv_cam_cnt", "bus_stop_cnt"]


def load_entropy_weights():
    path = os.path.join(OUTPUT_DIR, "09_엔트로피_가중치.csv")
    w = {}
    with open(path, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            w[row["인자"]] = float(row["가중치"])
    return w


def accident_epdo_point_in_polygon(grid_gdf, acc_gdf):
    """13번 교통사고이력 + 02번 격자 point-in-polygon"""
    acc_gdf = acc_gdf.to_crs(grid_gdf.crs)
    result = []
    for idx, row in grid_gdf.iterrows():
        gid = row["gid"]
        poly = row.geometry
        pts = acc_gdf[acc_gdf.intersects(poly)]
        cnt = {"사망": 0, "중상": 0, "경상": 0, "부상신고": 0, "상해없음": 0, "기타불명": 0}
        epdo = 0
        for _, p in pts.iterrows():
            sv = (p.get("injury_svrity") or "").strip()
            if "사망" in sv:
                cnt["사망"] += 1
                epdo += EPDO_WEIGHTS["사망"]
            elif "중상" in sv:
                cnt["중상"] += 1
                epdo += EPDO_WEIGHTS["중상"]
            elif "경상" in sv:
                cnt["경상"] += 1
                epdo += EPDO_WEIGHTS["경상"]
            elif "부상신고" in sv:
                cnt["부상신고"] += 1
                epdo += EPDO_WEIGHTS["부상신고"]
            elif "상해없음" in sv or sv == "":
                cnt["상해없음"] += 1
                epdo += EPDO_WEIGHTS["상해없음"]
            else:
                cnt["기타불명"] += 1
                epdo += EPDO_WEIGHTS["기타불명"]
        n = len(pts)
        result.append({
            "grid_gid": gid,
            "사고건수": n, "사망": cnt["사망"], "중상": cnt["중상"], "경상": cnt["경상"],
            "부상신고": cnt["부상신고"], "상해없음": cnt["상해없음"],
            "EPDO점수": epdo,
        })
    return pd.DataFrame(result)


def calc_gap_from_infra(infra_df, safety_cols):
    """00_격자별_통합데이터 기반 gap_cnt, gap_items"""
    means = {c: infra_df[c].fillna(0).replace("", 0).astype(float).mean() for c in safety_cols}
    def _gap(r):
        gaps = []
        for c in safety_cols:
            v = float(r.get(c, 0) or 0)
            if v == 0:
                gaps.append(f"{c}(없음)")
            elif means[c] > 0 and v < means[c] * 0.5:
                gaps.append(f"{c}(부족)")
        return len(gaps), " | ".join(gaps) if gaps else "-"
    infra_df = infra_df.copy()
    res = infra_df.apply(_gap, axis=1)
    infra_df["gap_cnt"] = [r[0] for r in res]
    infra_df["gap_items"] = [r[1] for r in res]
    return infra_df


def main():
    print("[1/5] 하남교산 격자 로드...")
    grid_path = os.path.join(DATA_DIR, "02._격자_(하남교산).geojson")
    grid_gdf = gpd.read_file(grid_path)
    grid_gdf["gid"] = grid_gdf["gid"].astype(str)
    hanam_gids = set(grid_gdf["gid"])

    print("[2/5] 교통사고 point-in-polygon (13번 → 02번)...")
    acc_path = os.path.join(DATA_DIR, "13._교통사고이력.geojson")
    acc_gdf = gpd.read_file(acc_path)
    acc_agg = accident_epdo_point_in_polygon(grid_gdf, acc_gdf)
    acc_agg = acc_agg[acc_agg["사고건수"] > 0]
    acc_gids = set(acc_agg["grid_gid"].astype(str))
    print(f"    사고발생 격자: {len(acc_gids)}개")

    print("[3/5] 08_격자_종합위험지수에서 7개 인자 + gap_items...")
    risk_path = os.path.join(OUTPUT_DIR, "08_격자_종합위험지수.csv")
    risk = pd.read_csv(risk_path, encoding="utf-8-sig")
    risk_hanam = risk[risk["grid_gid"].astype(str).isin(hanam_gids)].copy()

    print("[4/5] 00_격자별_통합데이터로 gap 보완 (08에 없는 격자)...")
    infra_path = os.path.join(OUTPUT_DIR, "00_격자별_통합데이터.csv")
    infra = pd.read_csv(infra_path, encoding="utf-8-sig")
    infra_hanam = infra[infra["grid_gid"].astype(str).isin(hanam_gids)].copy()
    infra_hanam = calc_gap_from_infra(infra_hanam, SAFETY_COLS)

    merged = acc_agg.merge(
        risk_hanam[["grid_gid"] + FACTOR_COLS + ["gap_items"]],
        on="grid_gid", how="left"
    )
    merged = merged.merge(
        infra_hanam[["grid_gid", "gap_cnt", "gap_items"]],
        on="grid_gid", how="left", suffixes=("", "_infra")
    )
    merged["gap_cnt"] = merged["gap_cnt"].fillna(merged["gap_cnt_infra"]).astype(int)
    merged["gap_items"] = merged["gap_items"].fillna(merged["gap_items_infra"])
    merged["핵심_인프라공백"] = merged["gap_items"]
    for c in FACTOR_COLS:
        if c in merged.columns and c != "gap_cnt":
            merged[c] = pd.to_numeric(merged[c], errors="coerce").fillna(0)
    merged["grid_avg_speed"] = pd.to_numeric(merged["grid_avg_speed"], errors="coerce").fillna(0)
    merged["grid_congestion"] = pd.to_numeric(merged["grid_congestion"], errors="coerce").fillna(0)

    print("[5/5] ECR(위험지수) 산출...")
    w = load_entropy_weights()
    for col in FACTOR_COLS:
        s = pd.to_numeric(merged[col], errors="coerce").fillna(0)
        mn, mx = s.min(), s.max()
        merged[f"_n_{col}"] = (s - mn) / (mx - mn) if (mx - mn) > 0 else 0.5
    merged["correction_index"] = sum(w.get(c, 0) * merged[f"_n_{c}"] for c in FACTOR_COLS if c in w)
    merged["entropy_composite_risk"] = (merged["EPDO점수"] * (1 + merged["correction_index"])).round(2)
    merged["correction_index"] = merged["correction_index"].round(6)

    merged["위험등급"] = merged["entropy_composite_risk"].apply(
        lambda x: "고위험" if x >= 111.12 else ("중위험" if x >= 77.38 else "저위험")
    )

    fac_path = os.path.join(OUTPUT_DIR, "12_facility_recommendation", "하남교산_시설추천.csv")
    fac = pd.read_csv(fac_path, encoding="utf-8-sig")
    fac = fac.rename(columns={"gid": "grid_gid"}) if "gid" in fac.columns else fac
    merged = merged.merge(fac[["grid_gid", "추천시설물"]], on="grid_gid", how="left")
    merged["추천시설물"] = merged["추천시설물"].fillna("")

    out_cols = [
        "grid_gid", "사고건수", "사망", "중상", "경상", "부상신고", "상해없음", "EPDO점수",
        "elderly_res_ratio", "vuln_float_ratio", "vuln_peak_pop", "weekend_ratio",
        "grid_avg_speed", "grid_congestion", "gap_cnt", "gap_items",
        "correction_index", "entropy_composite_risk", "위험등급", "핵심_인프라공백", "추천시설물"
    ]
    out = merged[[c for c in out_cols if c in merged.columns]].copy()
    out = out.sort_values("entropy_composite_risk", ascending=False)

    out_path = os.path.join(OUTPUT_DIR, "08_하남교산_격자별_ECR_최종.csv")
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n저장: {out_path}")
    print(f"격자 수: {len(out)}개")
    print("\nTop 10 (위험지수 기준):")
    for i, r in out.head(10).iterrows():
        print(f"  {r['grid_gid']:12s} 위험지수={r['entropy_composite_risk']:>7.2f}  {r['추천시설물']}")


if __name__ == "__main__":
    main()
