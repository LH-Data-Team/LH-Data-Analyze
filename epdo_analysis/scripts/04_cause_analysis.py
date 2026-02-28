"""
STEP 04 - 위험 도로 원인 분석
- 입력: epdo_analysis/output/01_사고별_EPDO점수.csv
        epdo_analysis/output/03_링크별_위험도.csv
- 출력: epdo_analysis/output/04_위험도로_원인분석.csv

선정 기준: epdo_rate 기준 상위 20개 (사고 3건 이상 링크만 대상)
  - 사고 1~2건 링크는 노출량이 작아 rate가 극단적으로 높아지므로 제외
분석 항목: violation, acc_type, road_type(road_rank), acc_time, week_type
"""

import csv
import os
from collections import Counter, defaultdict

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EPDO_FILE    = os.path.join(BASE_DIR, "epdo_analysis", "output", "01_사고별_EPDO점수.csv")
RISK_FILE    = os.path.join(BASE_DIR, "epdo_analysis", "output", "03_링크별_위험도.csv")
OUTPUT_PATH  = os.path.join(BASE_DIR, "epdo_analysis", "output", "04_위험도로_원인분석.csv")

MIN_ACCIDENT = 3    # 최소 사고 건수 기준
TOP_N        = 20   # 분석 대상 상위 링크 수


def top_item(counter, n=3):
    return " | ".join(f"{k}({v}건)" for k, v in counter.most_common(n))


def main():
    print("=" * 60)
    print("STEP 04 - 위험 도로 원인 분석")
    print("=" * 60)

    # 1. 위험도 로드 → 상위 링크 선정
    print(f"\n[1] 위험도 로드 중 (사고 {MIN_ACCIDENT}건 이상, 상위 {TOP_N}개)...")
    risk_rows = []
    with open(RISK_FILE, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["epdo_rate"] and int(row["accident_cnt"]) >= MIN_ACCIDENT:
                risk_rows.append(row)

    risk_rows.sort(key=lambda x: -float(x["epdo_rate"]))
    top_links = risk_rows[:TOP_N]
    top_link_ids = {r["link_id"] for r in top_links}
    print(f"    대상 링크: {len(top_links)}개")

    # 2. 사고 데이터 로드
    print("\n[2] 사고 데이터 로드 중...")
    accidents_by_link = defaultdict(list)
    all_accidents = []

    with open(EPDO_FILE, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            all_accidents.append(row)
            if row["link_id"] in top_link_ids:
                accidents_by_link[row["link_id"]].append(row)

    # 3. 전체 평균 분포 (비교 기준)
    all_violation = Counter(r["violation"] for r in all_accidents)
    all_acc_type  = Counter(r["acc_type"]  for r in all_accidents)
    all_time      = Counter(r["acc_time"]  for r in all_accidents)
    all_week      = Counter(r["week_type"] for r in all_accidents)
    total_all     = len(all_accidents)

    # 4. 링크별 원인 분석
    print("\n[3] 원인 분석 중...")
    result = []

    for r in top_links:
        lid  = r["link_id"]
        accs = accidents_by_link[lid]
        cnt  = len(accs)

        v_cnt   = Counter(a["violation"] for a in accs)
        t_cnt   = Counter(a["acc_type"]  for a in accs)
        time_cnt = Counter(a["acc_time"] for a in accs)
        week_cnt = Counter(a["week_type"] for a in accs)
        svr_cnt  = Counter(a["injury_svrity"] for a in accs)

        # 주말 비율
        weekend_ratio = round(week_cnt.get("주말", 0) / cnt * 100, 1) if cnt else 0

        # 전체 대비 특이 위반 (비율 차이)
        top_v = v_cnt.most_common(1)[0][0] if v_cnt else ""
        top_v_ratio = round(v_cnt.get(top_v, 0) / cnt * 100, 1)
        all_v_ratio = round(all_violation.get(top_v, 0) / total_all * 100, 1)

        result.append({
            "epdo_rank":         r["epdo_rank"],
            "link_id":           lid,
            "road_name":         r["road_name"],
            "road_rank":         r["road_rank"],
            "accident_cnt":      cnt,
            "epdo_total":        r["epdo_total"],
            "epdo_rate":         r["epdo_rate"],
            # 원인 분석
            "top_violation":     top_item(v_cnt, 3),
            "top_violation_1st": top_v,
            "top_v_ratio_pct":   top_v_ratio,
            "all_v_ratio_pct":   all_v_ratio,   # 전체 평균 비율
            "top_acc_type":      top_item(t_cnt, 2),
            "peak_time":         top_item(time_cnt, 3),
            "weekend_ratio_pct": weekend_ratio,
            "severity_dist":     top_item(svr_cnt, 4),
        })

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    cols = list(result[0].keys())
    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(result)

    print(f"\n[결과] 위험 도로 {len(result)}개 원인 분석 완료")
    print(f"\n{'순위':>4} {'도로명':20s} {'사고':>4} {'epdo_rate':>12} {'주요위반'}")
    print("-" * 80)
    for r in result[:10]:
        print(f"  {r['epdo_rank']:>3} {r['road_name']:20s} {r['accident_cnt']:>4}건 "
              f"{float(r['epdo_rate']):>12.1f}  {r['top_violation_1st']}")

    print(f"\n저장: {OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
