"""
STEP 08 - 격자 종합 위험 지수 산출 (v3 - 사고발생 격자 전체 대상)
- 입력:
    epdo_analysis/output/05_격자별_EPDO_인프라통합.csv  (기준: 사고발생 격자)
    epdo_analysis/output/07_링크_속도혼잡_보강.csv     (링크별 속도·혼잡 ← STEP 07)
    data/01._격자_(4개_시·구).geojson                  (격자 폴리곤)
    data/03._성연령별_거주인구(격자).csv                (gid → 노인 거주 인구)
    data/04._성연령별_유동인구.csv                      (lon/lat → 어린이·노인 유동인구)
    data/05._시간대별_직장인구.csv                      (lon/lat → 시간대별 직장인구)
    data/06._시간대별_방문인구.csv                      (lon/lat → 시간대별 방문인구)
    data/07._주중주말_서비스인구.csv                    (lon/lat → 주중/주말 인구)
    data/08.상세도로망_네트워크.geojson                 (링크 중심 → 격자 속도 집계용)
    data/22._토지이용계획도_(4개_신도시).geojson        (폴리곤 → 토지이용 유형)
    data/23._토지이용계획도_(하남교산).geojson          (하남교산 예측 위험도 출력용)
- 출력:
    epdo_analysis/output/08_격자_종합위험지수.csv       (사고발생 격자 종합 분석)
    epdo_analysis/output/08_하남교산_예측위험도.csv     (하남교산 신도시 예측)

수정 내역 (v2):
  1. CRS 경고 수정: centroid 계산 전 EPSG:5186(한국 중부원점) 재투영
  2. STEP 07 속도·혼잡 → 격자 단위 통합
     (도로망 링크 중심 → 격자 공간 join → 격자별 평균 속도·혼잡 집계)
  3. 토지이용 매칭률 개선: within → intersects (격자 폴리곤 기준)
  4. 23번 하남교산 예측 위험도 추가 출력
  5. "통행피크위험" 라벨 기준 개선: 중앙값 기준 상위 50%만 라벨 부여

종합 위험 지수 산출 공식:
  composite_risk = epdo_total
                   × vuln_correction   (교통약자 보정: 1 + 노인거주비율 + 어린이유동비율)
                   × infra_penalty     (인프라 공백: 1 + gap_cnt/9)
                   × speed_weight      (속도 보정: avg_speed/60, 없으면 1.0)
"""

import csv
import json
import os
import warnings
from collections import defaultdict, Counter

import geopandas as gpd
from shapely.geometry import Point

warnings.filterwarnings("ignore", category=UserWarning)   # CRS 관련 경고 억제

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 입력
INPUT_05     = os.path.join(BASE_DIR, "epdo_analysis", "output", "05_격자별_EPDO_인프라통합.csv")
STEP07_FILE  = os.path.join(BASE_DIR, "epdo_analysis", "output", "07_링크_속도혼잡_보강.csv")
GRID_FILE    = os.path.join(BASE_DIR, "data", "01._격자_(4개_시·구).geojson")
RES_FILE     = os.path.join(BASE_DIR, "data", "03._성연령별_거주인구(격자).csv")
FLOAT_FILE   = os.path.join(BASE_DIR, "data", "04._성연령별_유동인구.csv")
WORK_FILE    = os.path.join(BASE_DIR, "data", "05._시간대별_직장인구.csv")
VISIT_FILE   = os.path.join(BASE_DIR, "data", "06._시간대별_방문인구.csv")
SVC_FILE     = os.path.join(BASE_DIR, "data", "07._주중주말_서비스인구.csv")
ROAD_FILE    = os.path.join(BASE_DIR, "data", "08.상세도로망_네트워크.geojson")
LU_FILE      = os.path.join(BASE_DIR, "data", "22._토지이용계획도_(4개_신도시).geojson")
LU_HANAM     = os.path.join(BASE_DIR, "data", "23._토지이용계획도_(하남교산).geojson")

# 출력
OUTPUT_PATH  = os.path.join(BASE_DIR, "epdo_analysis", "output", "08_격자_종합위험지수.csv")
HANAM_OUTPUT = os.path.join(BASE_DIR, "epdo_analysis", "output", "08_하남교산_예측위험도.csv")

CRS_PROJ     = "EPSG:5186"   # 한국 중부원점 (단위: 미터, centroid 계산 정확)
CRS_GEO      = "EPSG:4326"   # WGS84

# 교통약자 취약 시간대: 등교(07~09), 하교(13~16), 퇴근(17~19)
VULN_SLOTS   = {7, 8, 9, 13, 14, 15, 16, 17, 18, 19}
SLOT_COLS    = [f"TMST_{str(h).zfill(2)}" for h in VULN_SLOTS]
ALL_SLOTS    = [f"TMST_{str(h).zfill(2)}" for h in range(24)]

# 토지이용 → 위험 카테고리 매핑
SCHOOL_TYPES    = {"학교", "초등학교", "중학교", "고등학교", "교육시설"}
RESIDENT_TYPES  = {"아파트", "연립주택", "다세대주택", "단독주택", "공동주택", "주상복합", "연립"}
COMMERCIAL_TYPES = {"상업", "일반상업", "근린상업", "근린생활시설용지", "상업시설"}
GAP_TARGET_COLS  = ["crosswalk_cnt", "child_zone_cnt", "speedbump_cnt",
                    "cctv_cnt", "cctv_cam_cnt", "bus_stop_cnt"]


# ── 유틸 ────────────────────────────────────────────────────────────────────

def load_csv_dict(path, key_col):
    with open(path, "r", encoding="utf-8-sig") as f:
        return {row[key_col]: row for row in csv.DictReader(f)}


def safe_float(val, default=0.0):
    try:
        return float(val or 0)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0):
    try:
        return int(float(val or 0))
    except (ValueError, TypeError):
        return default


def load_gap_data_from_05(path):
    """
    STEP 05 결과를 STEP 08 입력 형태(gap_data dict)로 변환
    - 기준: 사고가 1건 이상 발생한 격자 전체
    - gap_cnt/gap_items: 6개 안전시설 부재(<=0) 기준 산출
    """
    gap_data = {}
    with open(path, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            gid = str(row.get("grid_gid", "")).strip()
            if not gid:
                continue

            missing_items = []
            for col in GAP_TARGET_COLS:
                if safe_float(row.get(col, 0)) <= 0:
                    missing_items.append(f"{col}(없음)")

            gap_data[gid] = {
                "grid_gid": gid,
                "epdo_total": row.get("epdo_total", "0"),
                "accident_cnt": str(safe_int(row.get("accident_cnt", 0))),
                "사망_cnt": str(safe_int(row.get("사망_cnt", 0))),
                "중상_cnt": str(safe_int(row.get("중상_cnt", 0))),
                "school_cnt": str(safe_int(row.get("school_cnt", 0))),
                "kindergarten_cnt": str(safe_int(row.get("kindergarten_cnt", 0))),
                "gap_cnt": str(len(missing_items)),
                "gap_items": " | ".join(missing_items),
            }
    return gap_data


def points_to_grid(lon_col, lat_col, rows, value_cols, grid_gdf):
    """lon/lat 포인트 → 격자 공간 join 후 격자별 집계 반환"""
    pts = []
    for row in rows:
        try:
            lon, lat = float(row[lon_col]), float(row[lat_col])
        except (ValueError, KeyError):
            continue
        rec = {"geometry": Point(lon, lat)}
        for c in value_cols:
            rec[c] = safe_float(row.get(c))
        pts.append(rec)

    pts_gdf  = gpd.GeoDataFrame(pts, crs=CRS_GEO)
    joined   = gpd.sjoin(pts_gdf, grid_gdf[["gid", "geometry"]], how="left", predicate="within")
    return joined


def median(values):
    sv = sorted(v for v in values if v is not None)
    if not sv:
        return 0
    mid = len(sv) // 2
    return (sv[mid - 1] + sv[mid]) / 2 if len(sv) % 2 == 0 else sv[mid]


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("STEP 08 - 격자 종합 위험 지수 산출 (v3)")
    print("=" * 60)

    # ── 1. 사고발생 격자 목록 (STEP 05) ─────────────────────────────────────
    print("\n[1] 사고발생 격자 로드 중 (STEP 05)...")
    gap_data = load_gap_data_from_05(INPUT_05)
    print(f"    사고발생 격자 수: {len(gap_data):,}개")

    # ── 2. 격자 GeoDataFrame (사고발생 격자만 필터) ─────────────────────────
    print("\n[2] 격자 폴리곤 로드 중...")
    grid_gdf = gpd.read_file(GRID_FILE)
    grid_gdf = grid_gdf[grid_gdf["gid"].isin(gap_data.keys())].reset_index(drop=True)
    print(f"    사고발생 격자 폴리곤: {len(grid_gdf):,}개")

    # ── 3. STEP 07 속도·혼잡 → 격자 단위 집계 ───────────────────────────────
    # 개선 v3:
    #   [문제1] 중심점 기반 → 링크 선분 intersects 기반으로 변경
    #           (중심점이 다른 격자에 떨어지는 오류 해소)
    #   [문제2] 속도 미계측 링크 → 도로 등급별 평균으로 보간
    print("\n[3] STEP 07 속도·혼잡 → 격자 단위 집계 중...")
    step07 = load_csv_dict(STEP07_FILE, "link_id")

    # 도로망 로드 (speed 데이터 있는 링크만)
    road_gdf_all = gpd.read_file(ROAD_FILE)
    road_gdf_all["link_id"] = road_gdf_all["link_id"].astype(str)

    road_gdf_spd = road_gdf_all[road_gdf_all["link_id"].isin(step07.keys())].copy()

    # 속도·혼잡 컬럼 추가
    road_gdf_spd["avg_speed"]       = road_gdf_spd["link_id"].map(
        lambda lid: safe_float(step07.get(lid, {}).get("avg_speed")))
    road_gdf_spd["congestion_risk"] = road_gdf_spd["link_id"].map(
        lambda lid: safe_float(step07.get(lid, {}).get("congestion_risk")))

    # [문제1 해결] centroid 제거 → 선분 geometry 그대로 intersects 조인
    road_proj = road_gdf_spd.to_crs(CRS_PROJ)
    grid_proj = grid_gdf.to_crs(CRS_PROJ)

    link_grid = gpd.sjoin(
        road_proj[["link_id", "avg_speed", "congestion_risk", "geometry"]],
        grid_proj[["gid", "geometry"]],
        how="inner",
        predicate="intersects"   # 선분이 격자와 교차하면 모두 매칭
    )
    speed_agg = {}
    for gid, grp in link_grid.groupby("gid"):
        spd_vals = [v for v in grp["avg_speed"] if v > 0]
        cng_vals = [v for v in grp["congestion_risk"] if v > 0]
        speed_agg[str(gid)] = {
            "grid_avg_speed":       round(sum(spd_vals) / len(spd_vals), 2) if spd_vals else None,
            "grid_congestion_risk": round(sum(cng_vals) / len(cng_vals), 4) if cng_vals else None,
        }
    matched_before_interp = len(speed_agg)
    print(f"    [문제1 해결 후] 속도·혼잡 매칭 격자: {matched_before_interp:,}개 "
          f"({matched_before_interp/len(gap_data)*100:.1f}%)")

    # [문제2 해결] 속도 미계측 링크 → 도로 등급별 평균 보간
    # 1단계: 전체 도로망에서 road_rank별 평균 속도 계산 (계측 링크 기준)
    rank_speed_map = defaultdict(list)
    rank_cong_map  = defaultdict(list)
    for lid, data in step07.items():
        spd = safe_float(data.get("avg_speed"))
        cng = safe_float(data.get("congestion_risk"))
        # 해당 link_id의 road_rank 조회
        rank_rows = road_gdf_all[road_gdf_all["link_id"] == lid]
        if rank_rows.empty:
            continue
        rank = str(rank_rows.iloc[0].get("road_rank", ""))
        if spd > 0 and rank:
            rank_speed_map[rank].append(spd)
        if cng > 0 and rank:
            rank_cong_map[rank].append(cng)

    rank_avg_speed = {r: round(sum(v)/len(v), 2) for r, v in rank_speed_map.items()}
    rank_avg_cong  = {r: round(sum(v)/len(v), 4) for r, v in rank_cong_map.items()}
    overall_avg_speed = round(sum(rank_avg_speed.values())/len(rank_avg_speed), 2) \
                        if rank_avg_speed else 30.0
    overall_avg_cong  = round(sum(rank_avg_cong.values())/len(rank_avg_cong), 4) \
                        if rank_avg_cong else 0.0

    # 2단계: 결측 격자에 해당 격자 내 링크의 도로 등급별 평균 적용
    # 전체 도로망(속도 없는 링크 포함)과 격자 intersects 조인
    road_all_proj = road_gdf_all.to_crs(CRS_PROJ)
    link_grid_all = gpd.sjoin(
        road_all_proj[["link_id", "road_rank", "geometry"]],
        grid_proj[["gid", "geometry"]],
        how="inner",
        predicate="intersects"
    )
    interp_cnt = 0
    for gid, grp in link_grid_all.groupby("gid"):
        gid_str = str(gid)
        if gid_str in speed_agg:
            continue   # 이미 속도 데이터 있음
        # 격자 내 링크들의 도로 등급 목록
        ranks = [str(r) for r in grp["road_rank"].dropna() if str(r)]
        if not ranks:
            continue
        spd_vals = [rank_avg_speed.get(r, overall_avg_speed) for r in ranks]
        cng_vals = [rank_avg_cong.get(r,  overall_avg_cong)  for r in ranks]
        speed_agg[gid_str] = {
            "grid_avg_speed":       round(sum(spd_vals)/len(spd_vals), 2),
            "grid_congestion_risk": round(sum(cng_vals)/len(cng_vals), 4),
            "interpolated": True,   # 보간 여부 표시
        }
        interp_cnt += 1

    total_matched = len(speed_agg)
    print(f"    [문제2 해결 후] 도로등급 보간 추가: {interp_cnt:,}개")
    print(f"    최종 속도·혼잡 커버 격자: {total_matched:,}개 "
          f"({total_matched/len(gap_data)*100:.1f}%)")
    print(f"    도로 등급별 기본 속도: { {k: v for k, v in sorted(rank_avg_speed.items())} }")

    # ── 4. 03번 거주인구 — gid 직접 join ────────────────────────────────────
    print("\n[4] 거주인구(노인 60대+) 로드 중...")
    res_data = {}
    ELDERLY_COLS = ["m_60g_pop", "w_60g_pop", "m_70g_pop", "w_70g_pop",
                    "m_80g_pop", "w_80g_pop", "m_90g_pop", "w_90g_pop",
                    "m_100g_pop", "w_100g_pop"]
    ALL_RES_COLS = ["m_20g_pop", "w_20g_pop", "m_30g_pop", "w_30g_pop",
                    "m_40g_pop", "w_40g_pop", "m_50g_pop", "w_50g_pop"] + ELDERLY_COLS
    with open(RES_FILE, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            gid = row.get("gid", "")
            if gid not in gap_data:
                continue
            elderly = sum(safe_float(row.get(c)) for c in ELDERLY_COLS)
            total   = sum(safe_float(row.get(c)) for c in ALL_RES_COLS)
            res_data[gid] = {"elderly_pop": elderly, "total_res_pop": total}
    print(f"    거주인구 매칭 격자: {len(res_data):,}개 "
          f"(비어있는 격자는 거주인구 0으로 처리)")

    # ── 5. 04번 유동인구 — 공간 join ────────────────────────────────────────
    print("\n[5] 유동인구(어린이·노인) 공간 join 중...")
    float_cols = ["m_10g_pop", "w_10g_pop", "m_60g_pop", "w_60g_pop",
                  "m_20g_pop", "w_20g_pop", "m_30g_pop", "w_30g_pop",
                  "m_40g_pop", "w_40g_pop", "m_50g_pop", "w_50g_pop"]
    with open(FLOAT_FILE, "r", encoding="utf-8-sig") as f:
        float_rows = list(csv.DictReader(f))
    float_joined = points_to_grid("lon", "lat", float_rows, float_cols, grid_gdf)

    float_agg = {}
    for gid, grp in float_joined.dropna(subset=["gid"]).groupby("gid"):
        child   = grp["m_10g_pop"].sum() + grp["w_10g_pop"].sum()
        elderly = grp["m_60g_pop"].sum() + grp["w_60g_pop"].sum()
        total   = sum(grp[c].sum() for c in float_cols)
        float_agg[str(gid)] = {
            "child_float":   round(child, 4),
            "elderly_float": round(elderly, 4),
            "total_float":   round(total, 4),
        }
    print(f"    유동인구 매칭 격자: {len(float_agg):,}개")

    # ── 6. 05번 직장인구 — 취약 시간대 공간 join ────────────────────────────
    print("\n[6] 직장인구(취약 시간대) 공간 join 중...")
    with open(WORK_FILE, "r", encoding="utf-8-sig") as f:
        work_rows = list(csv.DictReader(f))
    work_joined = points_to_grid("lon", "lat", work_rows, SLOT_COLS + ALL_SLOTS, grid_gdf)

    work_agg = {}
    for gid, grp in work_joined.dropna(subset=["gid"]).groupby("gid"):
        vuln  = sum(grp[c].sum() for c in SLOT_COLS if c in grp.columns)
        total = sum(grp[c].sum() for c in ALL_SLOTS if c in grp.columns)
        work_agg[str(gid)] = {
            "vuln_work":  round(vuln, 4),
            "total_work": round(total, 4),
        }
    print(f"    직장인구 매칭 격자: {len(work_agg):,}개")

    # ── 7. 06번 방문인구 — 취약 시간대 공간 join ────────────────────────────
    print("\n[7] 방문인구(취약 시간대) 공간 join 중...")
    with open(VISIT_FILE, "r", encoding="utf-8-sig") as f:
        visit_rows = list(csv.DictReader(f))
    visit_joined = points_to_grid("lon", "lat", visit_rows, SLOT_COLS + ALL_SLOTS, grid_gdf)

    visit_agg = {}
    for gid, grp in visit_joined.dropna(subset=["gid"]).groupby("gid"):
        vuln  = sum(grp[c].sum() for c in SLOT_COLS if c in grp.columns)
        total = sum(grp[c].sum() for c in ALL_SLOTS if c in grp.columns)
        visit_agg[str(gid)] = {
            "vuln_visit":  round(vuln, 4),
            "total_visit": round(total, 4),
        }
    print(f"    방문인구 매칭 격자: {len(visit_agg):,}개")

    # ── 8. 07번 서비스인구 — 주중/주말 분리 공간 join ───────────────────────
    print("\n[8] 서비스인구(주중/주말) 공간 join 중...")
    svc_h, svc_w = [], []
    with open(SVC_FILE, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            (svc_h if row.get("hw") == "H" else svc_w).append(row)

    def agg_svc(rows, prefix):
        joined = points_to_grid("lon", "lat", rows, ["w_pop", "v_pop"], grid_gdf)
        agg = {}
        for gid, grp in joined.dropna(subset=["gid"]).groupby("gid"):
            agg[str(gid)] = {
                f"{prefix}_work":  round(grp["w_pop"].sum(), 4),
                f"{prefix}_visit": round(grp["v_pop"].sum(), 4),
            }
        return agg

    wd_agg = agg_svc(svc_h, "weekday")
    we_agg = agg_svc(svc_w, "weekend")
    print(f"    주중 매칭: {len(wd_agg):,}개 | 주말 매칭: {len(we_agg):,}개")

    # ── 9. 22번 토지이용 — 수정 2: intersects로 매칭률 개선 ─────────────────
    print("\n[9] 토지이용(4개 신도시) 공간 join 중...")
    lu_gdf = gpd.read_file(LU_FILE)

    # within → intersects: 격자 폴리곤과 토지이용 폴리곤이 조금이라도 겹치면 매칭
    lu_joined = gpd.sjoin(
        grid_gdf[["gid", "geometry"]],
        lu_gdf[["blockType", "geometry"]],
        how="left",
        predicate="intersects"
    )
    lu_map = {}
    for gid, grp in lu_joined.dropna(subset=["blockType"]).groupby("gid"):
        lu_map[str(gid)] = grp["blockType"].value_counts().idxmax()
    print(f"    토지이용 매칭 격자: {len(lu_map):,}개 "
          f"({len(lu_map)/len(gap_data)*100:.1f}%)")

    # ── 10. 종합 위험 지수 산출 ───────────────────────────────────────────────
    print("\n[10] 종합 위험 지수 산출 중...")

    # 취약 시간대 인구 중앙값 계산 (통행피크 라벨 기준)
    vuln_pops = []
    for gid in gap_data:
        vw = work_agg.get(gid, {}).get("vuln_work", 0)
        vv = visit_agg.get(gid, {}).get("vuln_visit", 0)
        vuln_pops.append(vw + vv)
    vuln_median = median(vuln_pops)

    # 교통약자 유동 비율 75번째 퍼센타일 계산 (교통약자유동多 라벨 기준 — 상위 25%만)
    # 고정 임계값 0.15는 99.2%가 해당되어 의미없으므로 분포 기반 동적 기준 적용
    vuln_float_vals = []
    for gid in gap_data:
        flt = float_agg.get(gid, {})
        cf = flt.get("child_float", 0)
        ef = flt.get("elderly_float", 0)
        tf = flt.get("total_float", 0)
        rt = round((cf + ef) / tf, 4) if tf > 0 else 0
        vuln_float_vals.append(rt)
    vuln_float_vals_sorted = sorted(vuln_float_vals)
    vuln_float_p75 = vuln_float_vals_sorted[int(len(vuln_float_vals_sorted) * 0.75)]
    print(f"    교통약자유동 75%ile 임계값: {vuln_float_p75:.4f} (상위 25% 기준 라벨 부여)")

    result = []
    for gid, gap in gap_data.items():
        epdo      = float(gap["epdo_total"])
        acc_cnt   = int(gap["accident_cnt"])
        death     = int(gap["사망_cnt"])
        heavy     = int(gap["중상_cnt"])
        gap_cnt        = int(gap["gap_cnt"])
        gap_items      = gap["gap_items"]
        # 학교인근 라벨용 교육시설 수 (공백 지표 제외이지만 라벨 판단에 사용)
        edu_cnt        = int(gap.get("school_cnt", 0) or 0) + int(gap.get("kindergarten_cnt", 0) or 0)

        # 거주인구 (03번)
        res            = res_data.get(gid, {})
        elderly_res    = res.get("elderly_pop", 0)
        total_res      = res.get("total_res_pop", 0)
        elderly_res_rt = round(elderly_res / total_res, 4) if total_res > 0 else 0

        # 유동인구 (04번)
        flt            = float_agg.get(gid, {})
        child_float    = flt.get("child_float", 0)
        elderly_float  = flt.get("elderly_float", 0)
        total_float    = flt.get("total_float", 0)
        vuln_float_rt  = round((child_float + elderly_float) / total_float, 4) \
                         if total_float > 0 else 0

        # 직장·방문인구 취약 시간대 (05·06번)
        vuln_work  = work_agg.get(gid, {}).get("vuln_work", 0)
        vuln_visit = visit_agg.get(gid, {}).get("vuln_visit", 0)
        vuln_peak  = vuln_work + vuln_visit

        # 서비스인구 주말 집중도 (07번)
        wd_visit      = wd_agg.get(gid, {}).get("weekday_visit", 0)
        we_visit      = we_agg.get(gid, {}).get("weekend_visit", 0)
        total_svc     = wd_visit + we_visit
        weekend_ratio = round(we_visit / total_svc, 4) if total_svc > 0 else 0

        # 속도·혼잡 (STEP 07 격자 집계)
        spd           = speed_agg.get(gid, {})
        grid_speed    = spd.get("grid_avg_speed")       # None 가능
        grid_cong     = spd.get("grid_congestion_risk") # None 가능
        speed_weight  = round(grid_speed / 60.0, 4) if grid_speed else 1.0

        # 토지이용 (22번)
        land_use = lu_map.get(gid, "미분류")

        # ── 보정계수 계산 ──────────────────────────────────────────────────
        # 1순위: 교통약자 보정 (03 거주인구 + 04 유동인구)
        vuln_ratio      = elderly_res_rt + vuln_float_rt
        vuln_correction = round(1.0 + vuln_ratio, 4)   # 최소 1.0

        # 인프라 공백 패널티 (6개 안전시설 기준, 분모 6으로 변경)
        # 교육시설(학교·유치원·어린이집)은 STEP 06에서 제외됨
        infra_penalty   = round(1.0 + gap_cnt / 6, 4)  # 최소 1.0, 최대 2.0

        # 2순위: 속도 보정 (09 평균속도)
        # speed_weight 이미 위에서 계산됨 (grid_speed / 60, 없으면 1.0)

        # 4순위: 혼잡강도 보정 (11 FRIN_CG × 12 TI_CG)
        # grid_congestion = FRIN_CG × TI_CG / 100 (범위 0~100)
        # 혼잡할수록 위험도 증가: 1.0(혼잡 없음) ~ 2.0(최대 혼잡)
        if grid_cong is not None:
            congestion_factor = round(1.0 + grid_cong / 100, 4)
        else:
            congestion_factor = 1.0

        # 5순위: 취약 시간대 인구 보정 (05 직장인구 + 06 방문인구)
        # vuln_peak / vuln_median 비율로 정규화
        # 중앙값의 2배 이상이면 최대 1.5배, 중앙값 이하면 1.0
        if vuln_median > 0 and vuln_peak > vuln_median:
            peak_ratio  = vuln_peak / vuln_median
            peak_factor = round(1.0 + min((peak_ratio - 1) * 0.3, 0.5), 4)
        else:
            peak_factor = 1.0

        # 5순위: 주말 방문인구 보정 (07 서비스인구)
        # weekend_ratio 0.5 초과분만큼 최대 25% 가중
        weekend_factor = round(1.0 + max(0.0, weekend_ratio - 0.5) * 0.5, 4)

        # 종합 위험 지수 (1~5순위 전체 반영)
        composite_risk  = round(
            epdo
            * vuln_correction    # 1순위: 교통약자 인구
            * infra_penalty      # 기존: 인프라 공백
            * speed_weight       # 2순위: 속도
            * congestion_factor  # 4순위: 혼잡강도
            * peak_factor        # 5순위: 취약시간 인구
            * weekend_factor,    # 5순위: 주말 방문
            2
        )

        # ── 위험 특성 라벨 (수정 3: 기준 명확화) ─────────────────────────
        labels = []
        if elderly_res_rt > 0.2:
            labels.append("노인밀집거주")
        if vuln_float_rt > vuln_float_p75:   # 상위 25%만 (동적 임계값 ~0.34)
            labels.append("교통약자유동多")
        if weekend_ratio > 0.55:
            labels.append("주말방문집중")
        if vuln_peak > vuln_median:           # 중앙값 초과만 라벨 부여
            labels.append("통행피크위험")
        if grid_speed and grid_speed >= 60:
            labels.append("고속도로위험")
        # 학교인근: land_use 기반(부지 내) + edu_cnt>0(격자 내 학교·유치원 존재) 모두 포함
        if land_use in SCHOOL_TYPES or edu_cnt > 0:
            labels.append("학교인근")
        if land_use in RESIDENT_TYPES:
            labels.append("주거밀집")
        if land_use in COMMERCIAL_TYPES:
            labels.append("상업지역")
        risk_label = " | ".join(labels) if labels else "일반"

        result.append({
            "grid_gid":          gid,
            "epdo_total":        epdo,
            "accident_cnt":      acc_cnt,
            "사망_cnt":           death,
            "중상_cnt":           heavy,
            # 교통약자 인구
            "elderly_res_pop":   round(elderly_res, 2),
            "elderly_res_ratio": elderly_res_rt,
            "child_float_pop":   round(child_float, 4),
            "elderly_float_pop": round(elderly_float, 4),
            "vuln_float_ratio":  vuln_float_rt,
            # 시간대 인구
            "vuln_time_work":    round(vuln_work, 4),
            "vuln_time_visit":   round(vuln_visit, 4),
            "vuln_peak_pop":     round(vuln_peak, 4),
            # 주말 집중도
            "weekend_ratio":     weekend_ratio,
            # 속도·혼잡 (격자 단위)
            "grid_avg_speed":    grid_speed if grid_speed is not None else "",
            "grid_congestion":   grid_cong  if grid_cong  is not None else "",
            # 인프라 공백
            "gap_cnt":           gap_cnt,
            "gap_items":         gap_items,
            # 토지이용
            "land_use":          land_use,
            # 보정계수 (1~5순위 전체)
            "vuln_correction":   vuln_correction,    # 1순위
            "infra_penalty":     infra_penalty,       # 기존
            "speed_weight":      speed_weight,        # 2순위 (grid_avg_speed / 60)
            "congestion_factor": congestion_factor,   # 4순위
            "peak_factor":       peak_factor,         # 5순위
            "weekend_factor":    weekend_factor,      # 5순위
            # 종합 위험 지수
            "composite_risk":    composite_risk,
            # 위험 라벨
            "risk_label":        risk_label,
        })

    result.sort(key=lambda x: -x["composite_risk"])
    for i, r in enumerate(result, 1):
        r["composite_rank"] = i

    # ── 11. 엔트로피 가중치 적용 종합 위험 지수 (STEP 09 결과 반영) ──────────
    print("\n[11] 엔트로피 가중치 적용 중...")

    # STEP 09 CSV에서 엔트로피 가중치 동적 로드 (하드코딩 제거)
    ENTROPY_W_PATH = os.path.join(BASE_DIR, "epdo_analysis", "output", "09_엔트로피_가중치.csv")
    ENTROPY_W = {}
    try:
        with open(ENTROPY_W_PATH, "r", encoding="utf-8-sig") as _f:
            for _row in csv.DictReader(_f):
                ENTROPY_W[_row["인자"]] = float(_row["가중치"])
        print(f"    엔트로피 가중치 로드: {ENTROPY_W_PATH}")
    except FileNotFoundError:
        # 09번 미실행 시 fallback — 최근 계산값 사용
        print(f"    ⚠ {ENTROPY_W_PATH} 없음 → fallback 가중치 사용")
        ENTROPY_W = {
            "elderly_res_ratio": 0.465370,
            "vuln_peak_pop":     0.362159,
            "grid_congestion":   0.067276,
            "grid_avg_speed":    0.048505,
            "weekend_ratio":     0.032431,
            "gap_cnt":           0.017510,
            "vuln_float_ratio":  0.006749,
        }

    def _minmax_norm(values):
        """None·빈문자열 포함 리스트를 0~1 정규화 (결측은 0 처리)"""
        nums = [float(v) for v in values if v is not None and v != ""]
        if not nums:
            return [0.0] * len(values)
        vmin, vmax = min(nums), max(nums)
        denom = vmax - vmin
        if denom == 0:
            return [0.5 if (v is not None and v != "") else 0.0 for v in values]
        return [
            (float(v) - vmin) / denom if (v is not None and v != "") else 0.0
            for v in values
        ]

    # 인자별 전체값 추출 → 정규화
    raw_vals = {k: [r.get(k, "") for r in result] for k in ENTROPY_W}
    norm_vals = {k: _minmax_norm(raw_vals[k]) for k in ENTROPY_W}

    # 각 격자에 엔트로피 가중 보정지수 + 새 종합 위험 지수 산출
    for i, r in enumerate(result):
        correction_index = sum(ENTROPY_W[k] * norm_vals[k][i] for k in ENTROPY_W)
        r["correction_index"]       = round(correction_index, 6)
        r["entropy_composite_risk"] = round(r["epdo_total"] * (1 + correction_index), 2)

    # 엔트로피 기준 재정렬 + 순위
    result.sort(key=lambda x: -x["entropy_composite_risk"])
    for i, r in enumerate(result, 1):
        r["entropy_rank"] = i

    print(f"    엔트로피 가중치 적용 완료: {len(result):,}개 격자")
    print(f"    가중치 구성: 노인거주({ENTROPY_W['elderly_res_ratio']:.1%}) "
          f"| 취약시간({ENTROPY_W['vuln_peak_pop']:.1%}) "
          f"| 혼잡({ENTROPY_W['grid_congestion']:.1%}) ...")

    # ── 12. 저장 ─────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    cols = list(result[0].keys())
    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(result)

    # ── 13. 하남교산 예측 위험도 — 엔트로피 기준으로 전이 ────────────────────
    print("\n[12] 하남교산 예측 위험도 산출 중...")

    # 4개 신도시에서 blockType별 평균 entropy_composite_risk 계산
    lu_risk = defaultdict(list)
    for r in result:
        if r["land_use"] != "미분류":
            lu_risk[r["land_use"]].append(r["entropy_composite_risk"])
    lu_avg_risk = {lt: round(sum(v) / len(v), 2) for lt, v in lu_risk.items()}

    # 등급 기준: lu_avg_risk 분포의 75·25 퍼센타일 사용
    all_risks   = [r["entropy_composite_risk"] for r in result]
    overall_avg = round(sum(all_risks) / len(all_risks), 2)
    lu_vals     = sorted(lu_avg_risk.values())
    def _pct(vals, p):
        idx = (p / 100) * (len(vals) - 1)
        lo, hi = int(idx), min(int(idx) + 1, len(vals) - 1)
        return vals[lo] + (idx - lo) * (vals[hi] - vals[lo])
    grade_high = _pct(lu_vals, 75)   # 상위 25% → 고위험
    grade_mid  = _pct(lu_vals, 25)   # 중위 50% → 중위험
    print(f"    등급 기준 - 고위험(75%ile): {grade_high:.1f} | "
          f"중위험(25~75%ile) | 저위험(<25%ile): {grade_mid:.1f}")

    # 23번 하남교산 토지이용 로드
    hanam_gdf   = gpd.read_file(LU_HANAM)
    hanam_result = []
    for _, feat in hanam_gdf.iterrows():
        btype    = feat.get("blockType", "미분류") or "미분류"
        btype    = btype.strip().replace("\r\n", "").replace("\n", "")
        # 동일 blockType 없으면 카테고리로 매칭
        if btype in lu_avg_risk:
            pred_risk = lu_avg_risk[btype]
            basis = "동일유형"
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
            pred_risk = overall_avg
            basis = "전체평균"

        # 위험 등급 분류 (4개 신도시 분포의 75·25 퍼센타일 기준)
        if pred_risk >= grade_high:
            risk_grade = "고위험"
        elif pred_risk >= grade_mid:
            risk_grade = "중위험"
        else:
            risk_grade = "저위험"

        hanam_result.append({
            "zoneCode":       feat.get("zoneCode", ""),
            "zoneName":       feat.get("zoneName", ""),
            "blockName":      feat.get("blockName", ""),
            "blockType":      btype,
            "pred_risk":      pred_risk,
            "risk_grade":     risk_grade,
            "basis":          basis,
        })

    hanam_result.sort(key=lambda x: -x["pred_risk"])
    with open(HANAM_OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(hanam_result[0].keys()))
        w.writeheader()
        w.writerows(hanam_result)

    hanam_high = sum(1 for r in hanam_result if r["risk_grade"] == "고위험")
    hanam_mid  = sum(1 for r in hanam_result if r["risk_grade"] == "중위험")
    hanam_low  = sum(1 for r in hanam_result if r["risk_grade"] == "저위험")
    print(f"    하남교산 전체 구역: {len(hanam_result):,}개")
    print(f"    고위험: {hanam_high}개 | 중위험: {hanam_mid}개 | 저위험: {hanam_low}개")

    # ── 결과 요약 ─────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"[최종 결과]")
    print(f"    분석 격자: {len(result):,}개")

    label_cnt = Counter()
    for r in result:
        for lb in r["risk_label"].split(" | "):
            if lb:
                label_cnt[lb] += 1
    print(f"\n    위험 특성 분포 (중앙값 기준 개선):")
    for lb, cnt in label_cnt.most_common():
        print(f"      {lb:15s}: {cnt:5d}개 ({cnt/len(result)*100:.1f}%)")

    print(f"\n    종합 위험 지수 상위 10개 (엔트로피 가중치 적용):")
    print(f"  {'순위':>4} {'격자ID':12s} {'EPDO':>6} "
          f"{'보정지수':>8} {'기존위험':>9} {'엔트로피위험':>12}  라벨")
    print("  " + "-" * 90)
    for r in result[:10]:
        print(f"  {r['entropy_rank']:>4} {r['grid_gid']:12s} {r['epdo_total']:>6.0f} "
              f"{r['correction_index']:>8.4f} {r['composite_risk']:>9.1f} "
              f"{r['entropy_composite_risk']:>12.1f}  {r['risk_label']}")

    print(f"\n    하남교산 고위험 구역 상위 5개:")
    print(f"  {'블록명':15s} {'유형':12s} {'예측위험':>8} {'등급':>5}")
    print("  " + "-" * 50)
    for r in hanam_result[:5]:
        print(f"  {str(r['blockName']):15s} {str(r['blockType']):12s} "
              f"{r['pred_risk']:>8.1f} {r['risk_grade']:>5}")

    print(f"\n저장: {OUTPUT_PATH}")
    print(f"저장: {HANAM_OUTPUT}")
    print("=" * 60)


if __name__ == "__main__":
    main()
