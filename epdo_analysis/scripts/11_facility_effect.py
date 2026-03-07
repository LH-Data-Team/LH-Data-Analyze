"""
STEP 11: 스마트 안전시설물 설치 효과 계량화
=============================================
문헌 기반 시설물별 사고 감소율을 적용하여
고위험 격자별 시설물 설치 후 예상 EPDO 감소량을 산출한다.

입력:
  epdo_analysis/output/06_인프라공백_고위험격자.csv
  epdo_analysis/output/08_격자_종합위험지수.csv   (entropy_rank 참조)

출력:
  epdo_analysis/output/11_시설물설치_효과예측.csv

방법론:
  - 문헌 기반 보수적 감소율 적용 (실증 전후 비교 데이터 부재 시 표준 접근법)
  - 독립 효과 가정: 총 감소율 = 1 - Π(1 - r_i)
  - 효율성 = EPDO 감소량 / 공백 시설물 수 (시설물 1개당 기대 효과)
  - 설치 우선순위 = 효율성 기준 내림차순

출처 근거 (보수적 하한값 적용):
  - 횡단보도 15%: 교통안전공단 (보행자 사고 15~25% 감소)
  - 어린이보호구역 25%: 행정안전부 (어린이 사고 30~40% 감소)
  - 과속방지턱 20%: 도로교통공단 (사고 20~30% 감소)
  - CCTV 개소 12%: 경찰청 (무인 단속 효과 10~20%)
  - CCTV 대수 5%: CCTV 개소와 중복 효과 최소화
  - 버스정류장 8%: 보행자 대기 공간 정비 효과
"""

import csv
import os

# ── 경로 설정 ─────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INPUT_GAP   = os.path.join(BASE_DIR, "epdo_analysis", "output", "06_인프라공백_고위험격자.csv")
INPUT_RISK  = os.path.join(BASE_DIR, "epdo_analysis", "output", "08_격자_종합위험지수.csv")
OUTPUT_PATH = os.path.join(BASE_DIR, "epdo_analysis", "output", "11_시설물설치_효과예측.csv")

# ── 시설물별 문헌 기반 보수적 사고 감소율 ──────────────────────────────────────
REDUCTION_RATES = {
    "crosswalk_cnt":  0.15,   # 횡단보도: 교통안전공단 15~25% → 하한 15%
    "child_zone_cnt": 0.25,   # 어린이보호구역: 행안부 30~40% → 하한 25%
    "speedbump_cnt":  0.20,   # 과속방지턱: 도로교통공단 20~30% → 하한 20%
    "cctv_cnt":       0.12,   # CCTV 개소: 경찰청 10~20% → 하한 12%
    "cctv_cam_cnt":   0.05,   # CCTV 대수: 개소 효과와 중복 최소화 → 5%
    "bus_stop_cnt":   0.08,   # 버스정류장: 보행자 대기 공간 정비 → 8%
}

FACILITY_KR = {
    "crosswalk_cnt":  "횡단보도",
    "child_zone_cnt": "어린이보호구역",
    "speedbump_cnt":  "과속방지턱",
    "cctv_cnt":       "CCTV(개소)",
    "cctv_cam_cnt":   "CCTV(대수)",
    "bus_stop_cnt":   "버스정류장",
}


def parse_gap_items(gap_str):
    """gap_items 문자열에서 공백 시설물 목록을 추출.
    예: "crosswalk_cnt(없음) | cctv_cnt(없음)" → {'crosswalk_cnt', 'cctv_cnt'}
    """
    if not gap_str or gap_str.strip() == "":
        return set()
    missing = set()
    for item in gap_str.split("|"):
        item = item.strip()
        if "(" in item:
            col = item.split("(")[0].strip()
            if col in REDUCTION_RATES:
                missing.add(col)
    return missing


def combined_reduction(missing_facilities):
    """독립 효과 가정: 총 감소율 = 1 - Π(1 - r_i)"""
    survive = 1.0
    for fac in missing_facilities:
        r = REDUCTION_RATES.get(fac, 0.0)
        survive *= (1.0 - r)
    return round(1.0 - survive, 6)


def main():
    # ── 1. 08번 파일에서 entropy_rank 로드 ──────────────────────────────────
    print("[1] entropy_rank 로드 중...")
    entropy_rank_map = {}
    entropy_risk_map = {}
    with open(INPUT_RISK, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            gid = row["grid_gid"]
            entropy_rank_map[gid] = row.get("entropy_rank", "")
            entropy_risk_map[gid] = row.get("entropy_composite_risk", "")
    print(f"    로드 완료: {len(entropy_rank_map):,}개 격자")

    # ── 2. 06번 공백 파일 로드 및 효과 계산 ──────────────────────────────────
    print("\n[2] 시설물 설치 효과 계산 중...")
    results = []
    facility_epdo_saved = {fac: 0.0 for fac in REDUCTION_RATES}

    with open(INPUT_GAP, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            gid       = row["grid_gid"]
            epdo_before = float(row.get("epdo_total", 0) or 0)
            acc_cnt   = int(row.get("accident_cnt", 0) or 0)
            death_cnt = int(row.get("사망_cnt", 0) or 0)
            injury_cnt= int(row.get("중상_cnt", 0) or 0)
            gap_cnt   = int(row.get("gap_cnt", 0) or 0)
            gap_items = row.get("gap_items", "")

            # 공백 시설물 파싱
            missing = parse_gap_items(gap_items)

            # 총 감소율 산출
            total_reduction = combined_reduction(missing)

            # 설치 후 예상 EPDO
            epdo_after = round(epdo_before * (1.0 - total_reduction), 2)
            epdo_saved = round(epdo_before - epdo_after, 2)

            # 효율성: 시설물 1개당 EPDO 감소량
            efficiency = round(epdo_saved / gap_cnt, 4) if gap_cnt > 0 else 0.0

            # 시설물별 기여 감소량 (단순 독립 분배: 각 시설의 단독 감소량)
            for fac in missing:
                r = REDUCTION_RATES.get(fac, 0)
                fac_saved = epdo_before * r
                facility_epdo_saved[fac] += fac_saved

            results.append({
                "grid_gid":            gid,
                "epdo_before":         epdo_before,
                "accident_cnt":        acc_cnt,
                "사망_cnt":            death_cnt,
                "중상_cnt":            injury_cnt,
                "gap_cnt":             gap_cnt,
                "missing_facilities":  " | ".join(sorted(missing)),
                "total_reduction_pct": round(total_reduction * 100, 2),
                "epdo_after":          epdo_after,
                "epdo_saved":          epdo_saved,
                "efficiency":          efficiency,
                "entropy_rank":        entropy_rank_map.get(gid, ""),
                "entropy_risk":        entropy_risk_map.get(gid, ""),
            })

    print(f"    계산 완료: {len(results):,}개 격자")

    # ── 3. 설치 우선순위: 효율성(시설물 1개당 EPDO 감소) 기준 ────────────────
    print("\n[3] 설치 우선순위 산출 중...")
    results.sort(key=lambda x: x["efficiency"], reverse=True)
    for i, row in enumerate(results, 1):
        row["install_priority"] = i

    # ── 4. CSV 저장 ─────────────────────────────────────────────────────────
    print("\n[4] CSV 저장 중...")
    fieldnames = [
        "install_priority", "grid_gid", "epdo_before", "accident_cnt",
        "사망_cnt", "중상_cnt", "gap_cnt", "missing_facilities",
        "total_reduction_pct", "epdo_after", "epdo_saved", "efficiency",
        "entropy_rank", "entropy_risk",
    ]
    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"    저장 완료: {OUTPUT_PATH}")

    # ── 5. 집계 요약 출력 ────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("  STEP 11 결과 요약")
    print("="*60)

    total_epdo_before = sum(r["epdo_before"] for r in results)
    total_epdo_saved  = sum(r["epdo_saved"]  for r in results)
    total_grids       = len(results)
    avg_reduction     = total_epdo_saved / total_epdo_before * 100 if total_epdo_before > 0 else 0

    print(f"\n  분석 대상 격자 수 : {total_grids:,}개")
    print(f"  현재 총 EPDO     : {total_epdo_before:,.0f}점")
    print(f"  설치 후 예상 EPDO: {(total_epdo_before - total_epdo_saved):,.0f}점")
    print(f"  총 예상 감소량   : {total_epdo_saved:,.0f}점 ({avg_reduction:.1f}%)")

    print("\n  [시설물 유형별 총 기여 감소량]")
    fac_sorted = sorted(facility_epdo_saved.items(), key=lambda x: x[1], reverse=True)
    for fac, saved in fac_sorted:
        pct = saved / total_epdo_before * 100 if total_epdo_before > 0 else 0
        print(f"    {FACILITY_KR.get(fac, fac):12s}: {saved:8,.0f}점 ({pct:.1f}%)")

    print("\n  [효율성 기준 설치 우선순위 Top-10]")
    print(f"  {'순위':>4} {'격자ID':12} {'현재EPDO':>8} {'감소율':>6} {'EPDO감소':>8} {'효율성':>8} {'entropy순위':>8}")
    for r in results[:10]:
        print(f"  {r['install_priority']:>4} {r['grid_gid']:12} "
              f"{r['epdo_before']:>8.0f} {r['total_reduction_pct']:>5.1f}% "
              f"{r['epdo_saved']:>8.0f} {r['efficiency']:>8.2f} "
              f"{r['entropy_rank']:>8}")

    print("\n  [EPDO 절대 감소량 기준 Top-10]")
    epdo_sorted = sorted(results, key=lambda x: x["epdo_saved"], reverse=True)
    print(f"  {'순위':>4} {'격자ID':12} {'현재EPDO':>8} {'감소율':>6} {'EPDO감소':>8} {'entropy순위':>8}")
    for i, r in enumerate(epdo_sorted[:10], 1):
        print(f"  {i:>4} {r['grid_gid']:12} "
              f"{r['epdo_before']:>8.0f} {r['total_reduction_pct']:>5.1f}% "
              f"{r['epdo_saved']:>8.0f} {r['entropy_rank']:>8}")

    print("="*60)


if __name__ == "__main__":
    main()
