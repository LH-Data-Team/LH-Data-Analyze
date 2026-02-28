"""
교통사고이력(13번)과 상세도로망(08번)을 매핑하는 스크립트
- 각 사고 지점(Point)에서 가장 가까운 도로 링크(LineString)를 찾아 link_id 부여
- 도로별 사고 건수 및 사고 uid 목록 집계
- 입력: data/08.상세도로망_네트워크.geojson, output/13._교통사고이력_uid.geojson
- 출력:
    output/13._교통사고_링크매핑.csv       (사고별: uid, link_id, 거리 등)
    output/13._링크별_사고집계.csv         (링크별: link_id, 사고건수, uid 목록)
"""

import json
import os
import csv
from shapely.geometry import shape, Point
from shapely.strtree import STRtree

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

ROAD_FILE = os.path.join(DATA_DIR, "08.상세도로망_네트워크.geojson")
ACCIDENT_FILE = os.path.join(OUTPUT_DIR, "13._교통사고이력_uid.geojson")
OUT_ACCIDENT = os.path.join(OUTPUT_DIR, "13._교통사고_링크매핑.csv")
OUT_LINK = os.path.join(OUTPUT_DIR, "13._링크별_사고집계.csv")


def main():
    print("=" * 60)
    print("교통사고 ↔ 도로 링크 매핑")
    print("=" * 60)

    # 1. 도로망 로드
    print("\n[1] 도로망 로드 중...")
    with open(ROAD_FILE, "r", encoding="utf-8") as f:
        road_data = json.load(f)

    links = []  # (link_id, road_name, geometry)
    for feat in road_data["features"]:
        props = feat["properties"]
        try:
            geom = shape(feat["geometry"])
            links.append({
                "link_id": props.get("link_id", ""),
                "road_name": props.get("road_name", ""),
                "road_rank": props.get("road_rank", ""),
                "max_speed": props.get("max_speed", ""),
                "length": props.get("length", ""),
                "geom": geom,
            })
        except Exception:
            pass

    link_geoms = [l["geom"] for l in links]
    tree = STRtree(link_geoms)
    print(f"    링크 수: {len(links):,}개")

    # 2. 교통사고 로드
    print("\n[2] 교통사고 로드 중...")
    with open(ACCIDENT_FILE, "r", encoding="utf-8") as f:
        accident_data = json.load(f)

    accidents = accident_data["features"]
    print(f"    사고 수: {len(accidents):,}건")

    # 3. 사고별 최근접 링크 매핑
    print("\n[3] 사고-링크 매핑 중...")
    accident_rows = []

    for acc in accidents:
        props = acc["properties"]
        uid = props.get("uid", "")
        coords = acc["geometry"]["coordinates"]
        lon, lat = coords[0], coords[1]
        pt = Point(lon, lat)

        idx = tree.nearest(pt)
        nearest = links[idx]
        dist_deg = pt.distance(nearest["geom"])
        dist_m = round(dist_deg * 111320, 2)

        accident_rows.append({
            "uid": uid,
            "lon": lon,
            "lat": lat,
            "link_id": nearest["link_id"],
            "road_name": nearest["road_name"],
            "road_rank": nearest["road_rank"],
            "max_speed": nearest["max_speed"],
            "length": nearest["length"],
            "distance_m": dist_m,
            "acc_yr": props.get("acc_yr", ""),
            "acc_mon": props.get("acc_mon", ""),
            "acc_time": props.get("acc_time", ""),
            "week_type": props.get("week_type", ""),
            "acc_type": props.get("acc_type", ""),
            "injury_svrity": props.get("injury_svrity", ""),
            "violation": props.get("violation", ""),
        })

    # 4. 사고별 결과 저장
    cols_acc = [
        "uid", "lon", "lat", "link_id", "road_name", "road_rank",
        "max_speed", "length", "distance_m",
        "acc_yr", "acc_mon", "acc_time", "week_type", "acc_type",
        "injury_svrity", "violation",
    ]
    with open(OUT_ACCIDENT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols_acc)
        w.writeheader()
        w.writerows(accident_rows)
    print(f"    저장: {OUT_ACCIDENT}")

    # 5. 링크별 집계
    print("\n[4] 링크별 집계 중...")
    link_map = {}
    for row in accident_rows:
        lid = row["link_id"]
        if lid not in link_map:
            link_map[lid] = {
                "link_id": lid,
                "road_name": row["road_name"],
                "road_rank": row["road_rank"],
                "max_speed": row["max_speed"],
                "length": row["length"],
                "accident_cnt": 0,
                "accident_uids": [],
            }
        link_map[lid]["accident_cnt"] += 1
        link_map[lid]["accident_uids"].append(str(row["uid"]))

    link_rows = sorted(link_map.values(), key=lambda x: -x["accident_cnt"])
    for r in link_rows:
        r["accident_uids"] = "|".join(r["accident_uids"])

    cols_link = [
        "link_id", "road_name", "road_rank", "max_speed", "length",
        "accident_cnt", "accident_uids",
    ]
    with open(OUT_LINK, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols_link)
        w.writeheader()
        w.writerows(link_rows)
    print(f"    저장: {OUT_LINK}")

    print(f"\n완료: 사고 {len(accident_rows):,}건 → 링크 {len(link_map):,}개 매핑")
    print(f"사고 최다 링크 Top5:")
    for r in link_rows[:5]:
        print(f"  link_id={r['link_id']} | {r['road_name']} | 사고 {r['accident_cnt']}건")
    print("=" * 60)


if __name__ == "__main__":
    main()
