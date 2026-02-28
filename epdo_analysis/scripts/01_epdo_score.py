"""
STEP 01 - 사고별 EPDO 점수 부여
- 입력: output/13._교통사고_링크매핑.csv
- 출력: epdo_analysis/output/01_사고별_EPDO점수.csv

EPDO 가중치 출처:
  이상엽(2019). 교통사고 원인행위의 벌점 추정에 관한 연구.
  대한교통학회지, 37(5), 365-378.
  사망=391, 중상=69, 경상=8, 부상신고=6, 물적피해(PDO)=1
"""

import csv
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INPUT_PATH  = os.path.join(BASE_DIR, "output", "13._교통사고_링크매핑.csv")
OUTPUT_PATH = os.path.join(BASE_DIR, "epdo_analysis", "output", "01_사고별_EPDO점수.csv")

EPDO_WEIGHTS = {
    "사망":   391,
    "중상":    69,
    "경상":     8,
    "부상신고":  6,
    "상해없음":  1,
    "기타불명":  8,   # 경상과 동일 (보수적 처리)
    "":          0,   # 차량단독·피해자 없음
}

def main():
    print("=" * 60)
    print("STEP 01 - 사고별 EPDO 점수 부여")
    print("=" * 60)

    with open(INPUT_PATH, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    print(f"\n입력 사고 수: {len(rows):,}건")

    result = []
    unknown = {}
    for row in rows:
        svrity = row.get("injury_svrity", "").strip()
        score = EPDO_WEIGHTS.get(svrity)
        if score is None:
            unknown[svrity] = unknown.get(svrity, 0) + 1
            score = 0
        result.append({
            "uid":           row["uid"],
            "link_id":       row["link_id"],
            "road_name":     row["road_name"],
            "injury_svrity": svrity,
            "epdo_score":    score,
            "acc_yr":        row["acc_yr"],
            "acc_mon":       row["acc_mon"],
            "acc_time":      row["acc_time"],
            "week_type":     row["week_type"],
            "acc_type":      row["acc_type"],
            "violation":     row["violation"],
            "road_type":     row.get("road_rank", ""),
            "lon":           row["lon"],
            "lat":           row["lat"],
        })

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    cols = list(result[0].keys())
    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(result)

    # 검증 출력
    from collections import Counter
    dist = Counter(r["injury_svrity"] for r in result)
    epdo_by_svrity = {}
    for r in result:
        k = r["injury_svrity"]
        epdo_by_svrity[k] = epdo_by_svrity.get(k, 0) + r["epdo_score"]

    total_epdo = sum(r["epdo_score"] for r in result)

    print(f"\n[심각도별 건수 및 EPDO 합계]")
    for k, cnt in dist.most_common():
        print(f"  {k or '(빈값)':10s}: {cnt:5d}건 | EPDO {epdo_by_svrity.get(k,0):,}점")

    print(f"\n전체 EPDO 합계: {total_epdo:,}점")
    print(f"저장: {OUTPUT_PATH}")

    if unknown:
        print(f"\n⚠ 미정의 값(0점 처리): {unknown}")

    print("=" * 60)


if __name__ == "__main__":
    main()
