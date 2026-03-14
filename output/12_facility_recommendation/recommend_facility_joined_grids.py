from pathlib import Path

import geopandas as gpd
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_GRID = BASE_DIR / "data" / "02._격자_(하남교산).geojson"
INPUT_ACCIDENT = BASE_DIR / "output" / "13._교통사고_격자매핑.geojson"
INPUT_RISK_GRID = BASE_DIR / "02_data_analysis" / "하남교산시_위험격자.geojson"
INPUT_WEIGHT = BASE_DIR / "epdo_analysis" / "output" / "10_통합가중치_최종.csv"
INPUT_SCHOOL = BASE_DIR / "data" / "15._학교현황.csv"
INPUT_KINDERGARTEN = BASE_DIR / "data" / "16._유치원현황.csv"

OUT_CSV = BASE_DIR / "12_facility_recommendation" / "하남교산_시설추천.csv"
OUT_GEOJSON = BASE_DIR / "12_facility_recommendation" / "하남교산_시설추천.geojson"

CHILD_ZONE_EDU_RADIUS_M = 300.0


REDUCTION_RATES = {
    "crosswalk_cnt": 0.15,
    "child_zone_cnt": 0.25,
    "speedbump_cnt": 0.20,
    "cctv_cnt": 0.12,
    "cctv_cam_cnt": 0.05,
    "bus_stop_cnt": 0.08,
}

FACILITY_LABEL = {
    "crosswalk_cnt": "스마트 횡단보도",
    "child_zone_cnt": "어린이보호구역 보강",
    "speedbump_cnt": "방지턱+노면표시",
    "cctv_cnt": "지능형 CCTV",
    "cctv_cam_cnt": "지능형 CCTV",
    "bus_stop_cnt": "버스정류장 연계 보행안전시설",
}


FACILITY_FACTOR_PROFILE = {
    "crosswalk_cnt": {
        "vuln_peak_pop": 1.0,
        "weekend_ratio": 0.7,
        "elderly_res_ratio": 0.8,
        "grid_congestion": 0.4,
    },
    "child_zone_cnt": {
        "elderly_res_ratio": 0.9,
        "vuln_float_ratio": 0.8,
        "vuln_peak_pop": 0.6,
        "weekend_ratio": 0.3,
    },
    "speedbump_cnt": {
        "grid_avg_speed": 1.0,
        "grid_congestion": 0.6,
        "vuln_peak_pop": 0.6,
    },
    "cctv_cnt": {
        "weekend_ratio": 0.8,
        "vuln_peak_pop": 0.7,
        "grid_congestion": 0.5,
        "gap_cnt": 0.4,
    },
    "cctv_cam_cnt": {
        "weekend_ratio": 0.6,
        "vuln_peak_pop": 0.6,
        "grid_congestion": 0.4,
    },
    "bus_stop_cnt": {
        "vuln_peak_pop": 0.9,
        "weekend_ratio": 0.7,
        "elderly_res_ratio": 0.4,
    },
}


def safe_float(v, default=0.0) -> float:
    try:
        return float(v if v not in (None, "") else default)
    except Exception:
        return default


def safe_int(v, default=0) -> int:
    try:
        return int(float(v if v not in (None, "") else default))
    except Exception:
        return default


def load_weights(path: Path) -> dict:
    df = pd.read_csv(path, encoding="utf-8-sig")
    out = {}
    for _, row in df.iterrows():
        key = str(row.get("인자", "")).strip()
        if key:
            out[key] = safe_float(row.get("통합가중치", 0.0))
    return out


def parse_gap_items(gap_items: str):
    if gap_items is None or str(gap_items).strip() == "":
        return []
    tokens = [t.strip() for t in str(gap_items).split("|") if t.strip()]
    out = []
    for token in tokens:
        for fac_key in REDUCTION_RATES.keys():
            if fac_key in token:
                out.append(fac_key)
                break
    return sorted(set(out))


def minmax_normalize(df: pd.DataFrame, factor_keys):
    norm = {}
    for k in factor_keys:
        arr = pd.to_numeric(df[k], errors="coerce").fillna(0.0)
        vmin = float(arr.min())
        vmax = float(arr.max())
        den = vmax - vmin
        if den == 0:
            norm[k] = [0.5] * len(arr)
        else:
            norm[k] = ((arr - vmin) / den).tolist()
    return norm


def build_education_nearby_flags(grid_df: gpd.GeoDataFrame, radius_m: float) -> dict:
    if grid_df.empty:
        return {}

    if not INPUT_SCHOOL.exists() or not INPUT_KINDERGARTEN.exists():
        return {gid: False for gid in grid_df["gid"].astype(str)}

    school = pd.read_csv(INPUT_SCHOOL, encoding="utf-8-sig", usecols=["lon", "lat"])
    kinder = pd.read_csv(INPUT_KINDERGARTEN, encoding="utf-8-sig", usecols=["lon", "lat"])
    edu = pd.concat([school, kinder], ignore_index=True)
    edu["lon"] = pd.to_numeric(edu["lon"], errors="coerce")
    edu["lat"] = pd.to_numeric(edu["lat"], errors="coerce")
    edu = edu.dropna(subset=["lon", "lat"]).copy()
    if edu.empty:
        return {gid: False for gid in grid_df["gid"].astype(str)}

    edu_gdf = gpd.GeoDataFrame(
        edu,
        geometry=gpd.points_from_xy(edu["lon"], edu["lat"]),
        crs="EPSG:4326",
    )

    grid_m = grid_df[["gid", "geometry"]].copy().to_crs(epsg=5179)
    edu_m = edu_gdf.to_crs(epsg=5179)

    # 격자 중심점 기준 반경 내 교육시설(학교/유치원) 존재 여부
    buffers = grid_m.copy()
    buffers["geometry"] = buffers.geometry.centroid.buffer(radius_m)
    joined = gpd.sjoin(buffers, edu_m[["geometry"]], how="left", predicate="intersects")
    grouped = joined.groupby("gid")["index_right"].apply(lambda s: s.notna().any())
    flags = {str(gid): bool(v) for gid, v in grouped.items()}

    for gid in grid_df["gid"].astype(str):
        flags.setdefault(gid, False)
    return flags


def choose_risk_grade(score: float, q70: float, q40: float) -> str:
    if score >= q70:
        return "고위험"
    if score >= q40:
        return "중위험"
    return "저위험"


def main():
    if not INPUT_GRID.exists() or not INPUT_ACCIDENT.exists() or not INPUT_RISK_GRID.exists() or not INPUT_WEIGHT.exists():
        raise FileNotFoundError("입력 파일 경로를 확인하세요.")

    grid_scope = gpd.read_file(INPUT_GRID)
    acc = gpd.read_file(INPUT_ACCIDENT)
    risk_gdf = gpd.read_file(INPUT_RISK_GRID)

    grid_scope["gid"] = grid_scope["gid"].astype(str).str.strip()
    acc["grid_gid"] = acc["grid_gid"].astype(str).str.strip()
    risk_gdf["gid"] = risk_gdf["gid"].astype(str).str.strip()
    risk_gdf["entropy_composite_risk"] = pd.to_numeric(risk_gdf["entropy_composite_risk"], errors="coerce")

    gid_set = set(grid_scope["gid"])
    joined = acc[acc["grid_gid"].isin(gid_set)].copy()
    if joined.empty:
        raise ValueError("gid-grid_gid 기준으로 조인되는 사고 데이터가 없습니다.")

    joined_gids = set(joined["grid_gid"].unique())
    target = risk_gdf[risk_gdf["gid"].isin(joined_gids)].copy()
    target = target[target["entropy_composite_risk"].notna()].copy()
    if target.empty:
        raise ValueError("조인된 격자 중 entropy_composite_risk 유효값이 없습니다.")

    edu_nearby_flags = build_education_nearby_flags(target, CHILD_ZONE_EDU_RADIUS_M)

    factor_weights = load_weights(INPUT_WEIGHT)
    factor_keys = [k for k in factor_weights.keys() if k in target.columns]
    if not factor_keys:
        raise ValueError("통합가중치 인자 컬럼이 대상 데이터에 없습니다.")

    target = target.reset_index(drop=True)
    norm = minmax_normalize(target, factor_keys)

    rows = []
    for i, row in target.iterrows():
        gid = row["gid"]
        entropy_risk = safe_float(row.get("entropy_composite_risk", 0.0))
        epdo = safe_float(row.get("epdo_total", 0.0))
        death_cnt = safe_int(row.get("사망_cnt", 0))
        heavy_cnt = safe_int(row.get("중상_cnt", 0))
        missing = parse_gap_items(row.get("gap_items", ""))
        gap_txt = " / ".join(missing) if missing else "없음"

        severity_boost = 1.0 + (0.2 if death_cnt > 0 else 0.0) + (0.1 if heavy_cnt > 0 else 0.0)

        best = None
        filtered_child_zone = False
        for fac in missing:
            if fac == "child_zone_cnt" and not edu_nearby_flags.get(str(gid), False):
                filtered_child_zone = True
                continue

            reduction = REDUCTION_RATES.get(fac, 0.0)
            profile = FACILITY_FACTOR_PROFILE.get(fac, {})

            weighted_match = 0.0
            for k in factor_keys:
                weighted_match += factor_weights[k] * profile.get(k, 0.0) * norm[k][i]

            priority_score = entropy_risk * reduction * (1.0 + weighted_match) * severity_boost
            expected_epdo_saved = epdo * reduction

            cand = {
                "facility_key": fac,
                "facility_name": FACILITY_LABEL.get(fac, fac),
                "priority_score": round(priority_score, 6),
                "expected_epdo_saved": round(expected_epdo_saved, 2),
                "reduction_rate_pct": round(reduction * 100, 2),
                "weighted_match": round(weighted_match, 6),
            }
            if best is None or cand["priority_score"] > best["priority_score"]:
                best = cand

        if best is None:
            best = {
                "facility_key": "",
                "facility_name": "해당없음",
                "priority_score": 0.0,
                "expected_epdo_saved": 0.0,
                "reduction_rate_pct": 0.0,
                "weighted_match": 0.0,
            }

        rows.append(
            {
                "gid": gid,
                "entropy_composite_risk": round(entropy_risk, 2),
                "epdo_total": round(epdo, 2),
                "사망_cnt": death_cnt,
                "중상_cnt": heavy_cnt,
                "severity_boost": round(severity_boost, 2),
                "핵심_인프라공백": gap_txt,
                "교육시설근접(300m)": "Y" if edu_nearby_flags.get(str(gid), False) else "N",
                "child_zone_제외여부": "Y" if filtered_child_zone else "N",
                "제안시설": best["facility_name"],
                "facility_key": best["facility_key"],
                "priority_score": best["priority_score"],
                "expected_epdo_saved": best["expected_epdo_saved"],
                "reduction_rate_pct": best["reduction_rate_pct"],
                "weighted_match": best["weighted_match"],
            }
        )

    rec_df = pd.DataFrame(rows).sort_values("priority_score", ascending=False).reset_index(drop=True)
    q70 = rec_df["entropy_composite_risk"].quantile(0.70)
    q40 = rec_df["entropy_composite_risk"].quantile(0.40)
    rec_df["위험등급"] = rec_df["entropy_composite_risk"].apply(lambda x: choose_risk_grade(x, q70, q40))

    # 최종 산출물은 gid + 추천시설물만 저장
    result_df = rec_df[["gid", "제안시설"]].copy()
    result_df = result_df.rename(columns={"제안시설": "추천시설물"})

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    out_gdf = grid_scope.merge(result_df, how="inner", left_on="gid", right_on="gid")
    out_gdf = out_gdf[["gid", "추천시설물", "geometry"]].copy()
    out_gdf.to_file(OUT_GEOJSON, driver="GeoJSON")

    print(f"하남교산 전체 격자 수: {len(grid_scope):,}")
    print(f"조인된 사고 행 수: {len(joined):,}")
    print(f"조인된 고유 격자 수: {result_df['gid'].nunique():,}")
    print(f"추천 산출 격자 수: {len(result_df):,}")
    print(f"어린이보호구역 근접 가능 격자(300m): {sum(1 for v in edu_nearby_flags.values() if v):,}")
    print(f"저장 CSV: {OUT_CSV}")
    print(f"저장 GeoJSON: {OUT_GEOJSON}")


if __name__ == "__main__":
    main()
