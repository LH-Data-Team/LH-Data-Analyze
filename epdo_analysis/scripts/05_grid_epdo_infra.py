"""
STEP 05 - 격자별 EPDO + 인프라 통합 분석
- 입력: output/13._교통사고_격자매핑.geojson (사고별 grid_gid + injury_svrity)
        output/격자별_통합데이터.csv (grid_gid별 인프라 집계)
- 출력: epdo_analysis/output/05_격자별_EPDO_인프라통합.csv

EPDO 가중치 출처:
  이상엽(2019). 교통사고 원인행위의 벌점 추정에 관한 연구.
  대한교통학회지, 37(5), 365-378.
"""

import csv
import json
import os
from collections import defaultdict

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ACCIDENT_FILE = os.path.join(BASE_DIR, "output", "13._교통사고_격자매핑.geojson")
INFRA_FILE   = os.path.join(BASE_DIR, "output", "격자별_통합데이터.csv")
OUTPUT_PATH  = os.path.join(BASE_DIR, "epdo_analysis", "output", "05_격자별_EPDO_인프라통합.csv")

EPDO_WEIGHTS = {
    "사망":    391,
    "중상":     69,
    "경상":      8,
    "부상신고":   6,
    "상해없음":   1,
    "기타불명":   8,
    "":          0,
}

SEVERITY_KEYS = ["사망", "중상", "경상", "부상신고", "상해없음", "기타불명"]


def main():
    print("=" * 60)
    print("STEP 05 - 격자별 EPDO + 인프라 통합 분석")
    print("=" * 60)

    # 1. 사고 데이터 로드 → 격자별 EPDO 집계
    print("\n[1] 사고 데이터 로드 중...")
    with open(ACCIDENT_FILE, "r", encoding="utf-8") as f:
        accident_data = json.load(f)

    grid_epdo = defaultdict(lambda: {
        "epdo_total":  0.0,
        "accident_cnt": 0,
        **{f"{k}_cnt": 0 for k in SEVERITY_KEYS},
    })

    for feat in accident_data["features"]:
        props = feat["properties"]
        gid   = props.get("grid_gid", "")
        if not gid:
            continue
        svrity = (props.get("injury_svrity") or "").strip()
        score  = EPDO_WEIGHTS.get(svrity, 0)

        grid_epdo[gid]["epdo_total"]   += score
        grid_epdo[gid]["accident_cnt"] += 1
        key = f"{svrity}_cnt" if svrity in SEVERITY_KEYS else ""
        if key:
            grid_epdo[gid][key] += 1

    print(f"    사고 격자 수: {len(grid_epdo):,}개 / 전체 사고: {len(accident_data['features']):,}건")

    # 2. 인프라 데이터 로드
    print("\n[2] 인프라 데이터 로드 중...")
    infra = {}
    with open(INFRA_FILE, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            infra[row["grid_gid"]] = row

    print(f"    인프라 격자 수: {len(infra):,}개")

    # 3. 통합
    result = []
    matched = 0
    for gid, epdo in grid_epdo.items():
        epdo_total  = round(epdo["epdo_total"], 2)
        acc_cnt     = epdo["accident_cnt"]
        epdo_avg    = round(epdo_total / acc_cnt, 4) if acc_cnt else 0

        inf = infra.get(gid, {})
        if inf:
            matched += 1

        result.append({
            "grid_gid":          gid,
            "epdo_total":        epdo_total,
            "epdo_avg":          epdo_avg,
            "accident_cnt":      acc_cnt,
            "사망_cnt":           epdo["사망_cnt"],
            "중상_cnt":           epdo["중상_cnt"],
            "경상_cnt":           epdo["경상_cnt"],
            "부상신고_cnt":        epdo["부상신고_cnt"],
            "상해없음_cnt":        epdo["상해없음_cnt"],
            "기타불명_cnt":        epdo["기타불명_cnt"],
            "crosswalk_cnt":     inf.get("crosswalk_cnt", 0),
            "child_zone_cnt":    inf.get("child_zone_cnt", 0),
            "school_cnt":        inf.get("school_cnt", 0),
            "kindergarten_cnt":  inf.get("kindergarten_cnt", 0),
            "daycare_cnt":       inf.get("daycare_cnt", 0),
            "bus_stop_cnt":      inf.get("bus_stop_cnt", 0),
            "cctv_cnt":          inf.get("cctv_cnt", 0),
            "cctv_cam_cnt":      inf.get("cctv_cam_cnt", 0),
            "speedbump_cnt":     inf.get("speedbump_cnt", 0),
        })

    result.sort(key=lambda x: -x["epdo_total"])

    # 4. 저장
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    cols = list(result[0].keys())
    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(result)

    total_epdo = sum(r["epdo_total"] for r in result)
    print(f"\n[결과]")
    print(f"    격자 수: {len(result):,}개 | 인프라 매칭: {matched:,}개")
    print(f"    전체 EPDO 합계: {total_epdo:,.0f}점")
    print(f"\n    epdo_total 상위 10개:")
    print(f"  {'격자ID':12s} {'EPDO':>8} {'사고':>4} {'사망':>3} {'중상':>4} {'횡단보도':>6} {'CCTV':>5} {'과속방지턱':>7}")
    print("  " + "-" * 65)
    for r in result[:10]:
        print(f"  {r['grid_gid']:12s} {r['epdo_total']:>8.0f} {r['accident_cnt']:>4} "
              f"{r['사망_cnt']:>3} {r['중상_cnt']:>4} {r['crosswalk_cnt']:>6} "
              f"{r['cctv_cnt']:>5} {r['speedbump_cnt']:>7}")

    print(f"\n저장: {OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
