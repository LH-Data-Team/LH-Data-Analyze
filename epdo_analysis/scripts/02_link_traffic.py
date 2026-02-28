"""
STEP 02 - 링크별 교통량 집계
- 입력: data/08.상세도로망_네트워크.geojson (up_v_link, dw_v_link → link_id 매핑)
        data/10._추정교통량.csv (v_link_id, ALL_AADT, k_length)
- 출력: epdo_analysis/output/02_링크별_교통량.csv

노출량(exposure) = ALL_AADT_total × k_length (대·km/일)
"""

import csv
import json
import os
from collections import defaultdict

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROAD_FILE   = os.path.join(BASE_DIR, "data", "08.상세도로망_네트워크.geojson")
TRAFFIC_FILE = os.path.join(BASE_DIR, "data", "10._추정교통량.csv")
OUTPUT_PATH = os.path.join(BASE_DIR, "epdo_analysis", "output", "02_링크별_교통량.csv")


def main():
    print("=" * 60)
    print("STEP 02 - 링크별 교통량 집계")
    print("=" * 60)

    # 1. 08번에서 v_link_id → link_id 역매핑
    print("\n[1] 도로망 로드 중...")
    with open(ROAD_FILE, "r", encoding="utf-8") as f:
        road_data = json.load(f)

    vlink_to_link = {}   # v_link_id(str) → link_id(str)
    link_props    = {}   # link_id(str) → {road_name, road_rank, length, k_length}
    for feat in road_data["features"]:
        p = feat["properties"]
        lid = str(p["link_id"])
        link_props[lid] = {
            "road_name": p.get("road_name", ""),
            "road_rank": p.get("road_rank", ""),
            "length":    p.get("length", ""),
        }
        up = p.get("up_v_link")
        dw = p.get("dw_v_link")
        if up:
            vlink_to_link[str(up)] = lid
        if dw:
            vlink_to_link[str(dw)] = lid

    print(f"    링크 수: {len(link_props):,}")
    print(f"    v_link 매핑 수: {len(vlink_to_link):,}")

    # 2. 10번 교통량 집계 (timeslot별 ALL_AADT 합산)
    print("\n[2] 교통량 데이터 로드 중...")
    aadt_by_vlink  = defaultdict(float)
    klen_by_vlink  = {}
    rank_by_vlink  = {}

    with open(TRAFFIC_FILE, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            vid = row["v_link_id"]
            try:
                aadt_by_vlink[vid] += float(row["ALL_AADT"])
            except (ValueError, KeyError):
                pass
            klen_by_vlink[vid]  = row.get("k_length", "")
            rank_by_vlink[vid]  = row.get("road_rank", "")

    print(f"    v_link_id 수: {len(aadt_by_vlink):,}")

    # 3. v_link_id → link_id 변환 후 상행/하행 평균
    link_aadt = defaultdict(list)   # link_id → [aadt_values]
    link_klen = {}

    for vid, aadt in aadt_by_vlink.items():
        lid = vlink_to_link.get(vid)
        if lid:
            link_aadt[lid].append(aadt)
            if lid not in link_klen:
                link_klen[lid] = klen_by_vlink.get(vid, "")

    print(f"    link_id 매칭 수: {len(link_aadt):,} / {len(link_props):,}")

    # 4. 링크별 교통량 산출 (상행·하행 평균)
    result = []
    for lid, aadt_list in link_aadt.items():
        all_aadt_total = sum(aadt_list) / len(aadt_list)   # 방향 평균
        try:
            k_length = float(link_klen.get(lid, 0))
        except ValueError:
            k_length = 0.0
        exposure = all_aadt_total * k_length   # 대·km/일

        props = link_props.get(lid, {})
        result.append({
            "link_id":       lid,
            "road_name":     props.get("road_name", ""),
            "road_rank":     props.get("road_rank", ""),
            "length_km":     props.get("length", ""),
            "k_length":      k_length,
            "ALL_AADT_total": round(all_aadt_total, 2),
            "exposure":      round(exposure, 4),
        })

    result.sort(key=lambda x: -x["exposure"])

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    cols = list(result[0].keys())
    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(result)

    print(f"\n[결과] 교통량 산출 링크: {len(result):,}개")
    print(f"       노출량 상위 5개:")
    for r in result[:5]:
        print(f"  link_id={r['link_id']} | {r['road_name']} | AADT={r['ALL_AADT_total']:,.0f} | 노출량={r['exposure']:,.1f}")
    print(f"\n저장: {OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
