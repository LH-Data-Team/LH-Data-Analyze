"""
STEP 03 - 링크별 위험도 산출
- 입력: epdo_analysis/output/01_사고별_EPDO점수.csv
        epdo_analysis/output/02_링크별_교통량.csv
        output/13._링크별_사고집계.csv (accident_uids 참조)
- 출력: epdo_analysis/output/03_링크별_위험도.csv

위험도(epdo_rate) = epdo_total / exposure × 1,000,000
  (단위: 백만 대·km당 EPDO, 교통량 미매칭 링크는 null)
"""

import csv
import os
from collections import defaultdict

BASE_DIR      = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EPDO_FILE     = os.path.join(BASE_DIR, "epdo_analysis", "output", "01_사고별_EPDO점수.csv")
TRAFFIC_FILE  = os.path.join(BASE_DIR, "epdo_analysis", "output", "02_링크별_교통량.csv")
AGG_FILE      = os.path.join(BASE_DIR, "output", "13._링크별_사고집계.csv")
OUTPUT_PATH   = os.path.join(BASE_DIR, "epdo_analysis", "output", "03_링크별_위험도.csv")


def main():
    print("=" * 60)
    print("STEP 03 - 링크별 위험도 산출")
    print("=" * 60)

    # 1. 사고별 EPDO 집계
    print("\n[1] 사고별 EPDO 로드 중...")
    link_epdo    = defaultdict(float)
    link_cnt     = defaultdict(int)
    link_meta    = {}   # link_id → {road_name, road_rank, max_speed, length}

    with open(EPDO_FILE, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            lid = str(row["link_id"])
            link_epdo[lid] += float(row["epdo_score"])
            link_cnt[lid]  += 1
            if lid not in link_meta:
                link_meta[lid] = {
                    "road_name": row["road_name"],
                    "road_rank": row["road_type"],   # road_type에 road_rank 저장됨
                }

    print(f"    사고 매핑 링크 수: {len(link_epdo):,}")

    # 2. 교통량 로드
    print("\n[2] 교통량 로드 중...")
    traffic = {}
    with open(TRAFFIC_FILE, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            lid = str(row["link_id"])
            traffic[lid] = {
                "ALL_AADT_total": float(row["ALL_AADT_total"]),
                "exposure":       float(row["exposure"]),
                "k_length":       row["k_length"],
                "length_km":      row["length_km"],
                "road_rank":      row["road_rank"],
                "road_name":      row["road_name"],
            }

    # 3. accident_uids 로드
    uids_by_link = {}
    with open(AGG_FILE, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            uids_by_link[str(row["link_id"])] = row.get("accident_uids", "")

    # 4. 링크별 위험도 산출
    result = []
    matched = 0
    for lid, epdo_total in link_epdo.items():
        acc_cnt   = link_cnt[lid]
        epdo_avg  = round(epdo_total / acc_cnt, 4) if acc_cnt else 0
        meta      = link_meta.get(lid, {})
        traf      = traffic.get(lid)

        if traf and traf["exposure"] > 0:
            epdo_rate = round(epdo_total / traf["exposure"] * 1_000_000, 4)
            matched += 1
        else:
            epdo_rate = None

        result.append({
            "link_id":        lid,
            "road_name":      traf["road_name"] if traf else meta.get("road_name", ""),
            "road_rank":      traf["road_rank"] if traf else meta.get("road_rank", ""),
            "length_km":      traf["length_km"] if traf else "",
            "accident_cnt":   acc_cnt,
            "epdo_total":     round(epdo_total, 2),
            "epdo_avg":       epdo_avg,
            "ALL_AADT_total": round(traf["ALL_AADT_total"], 2) if traf else "",
            "exposure":       round(traf["exposure"], 4) if traf else "",
            "epdo_rate":      epdo_rate,
            "accident_uids":  uids_by_link.get(lid, ""),
        })

    # epdo_rate 기준 정렬 (null은 후순위)
    result.sort(key=lambda x: (x["epdo_rate"] is None, -(x["epdo_rate"] or 0)))

    # 순위 부여 (epdo_rate 있는 것만)
    rank = 1
    for r in result:
        if r["epdo_rate"] is not None:
            r["epdo_rank"] = rank
            rank += 1
        else:
            r["epdo_rank"] = ""

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    cols = ["link_id", "road_name", "road_rank", "length_km",
            "accident_cnt", "epdo_total", "epdo_avg",
            "ALL_AADT_total", "exposure", "epdo_rate", "epdo_rank",
            "accident_uids"]
    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(result)

    print(f"\n[결과]")
    print(f"    사고 발생 링크: {len(result):,}개")
    print(f"    교통량 매칭 링크: {matched:,}개 ({matched/len(result)*100:.1f}%)")
    print(f"\n    epdo_rate 상위 10개 (백만 대·km당 EPDO):")
    for r in result[:10]:
        print(f"  rank={r['epdo_rank']:>4} | {r['road_name']:20s} | "
              f"사고{r['accident_cnt']:3d}건 | epdo_total={r['epdo_total']:>8.1f} | "
              f"rate={r['epdo_rate']:>10.2f}")
    print(f"\n저장: {OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
