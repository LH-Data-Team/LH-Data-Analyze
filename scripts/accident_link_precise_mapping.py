"""
사고다발 링크(다사672368, accident_cnt 24) 추출 및 교통사고 위경도 ↔ 링크 정확 매핑
- 1. 해당 링크만 별도 CSV로 추출
- 2. 격자 내 교통사고(lon, lat)와 가장 가까운 링크 매핑
"""

import json
import os
import csv
from collections import Counter
from shapely.geometry import shape, Point

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
DATA_DIR = os.path.join(BASE_DIR, 'data')

LINK_GRID_FILE = os.path.join(OUTPUT_DIR, '08._도로망_link_격자매핑.csv')
ROAD_NETWORK_FILE = os.path.join(DATA_DIR, '08.상세도로망_네트워크.geojson')
ACCIDENT_GRID_FILE = os.path.join(OUTPUT_DIR, '13._교통사고_격자매핑.geojson')

OUTPUT_LINKS = os.path.join(OUTPUT_DIR, '사고다발_링크_다사672368.csv')
OUTPUT_ACCIDENT_LINK = os.path.join(OUTPUT_DIR, '교통사고_링크_정확매핑_다사672368.csv')

TARGET_GRID = '다사672368'


def main():
    print("=" * 60)
    print("사고다발 링크 추출 및 교통사고↔링크 정확 매핑")
    print("=" * 60)

    # 1. 다사672368 격자 링크만 추출
    target_links = []
    with open(LINK_GRID_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('grid_gid') == TARGET_GRID:
                target_links.append(row)

    link_ids = {int(r['link_id']) for r in target_links}
    print(f"\n[1] 추출 링크: {len(link_ids)}개 (grid={TARGET_GRID})")

    with open(OUTPUT_LINKS, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['link_id', 'grid_gid', 'accident_cnt'])
        w.writeheader()
        w.writerows(target_links)
    print(f"    저장: {OUTPUT_LINKS}")

    # 2. 08번 도로망에서 해당 link_id의 LineString 로드
    with open(ROAD_NETWORK_FILE, 'r', encoding='utf-8') as f:
        road_data = json.load(f)

    link_geoms = {}
    for feat in road_data['features']:
        lid = feat['properties'].get('link_id')
        if lid in link_ids:
            try:
                link_geoms[lid] = shape(feat['geometry'])
            except Exception:
                pass
    print(f"\n[2] 링크 geometry 로드: {len(link_geoms)}개")

    # 3. 교통사고 격자매핑에서 다사672368만 필터
    with open(ACCIDENT_GRID_FILE, 'r', encoding='utf-8') as f:
        accident_data = json.load(f)

    accidents_in_grid = [
        f for f in accident_data['features']
        if f.get('properties', {}).get('grid_gid') == TARGET_GRID
    ]
    print(f"\n[3] 격자 내 교통사고: {len(accidents_in_grid)}건")

    # 4. 각 사고 지점 → 가장 가까운 링크 매핑
    results = []
    for acc in accidents_in_grid:
        pt = shape(acc['geometry'])
        lon, lat = pt.x, pt.y
        props = acc.get('properties', {})

        min_dist = float('inf')
        nearest_link = None
        for lid, line in link_geoms.items():
            d = pt.distance(line)
            if d < min_dist:
                min_dist = d
                nearest_link = lid

        row = {
            'lon': lon,
            'lat': lat,
            'link_id': nearest_link or '',
            'distance_m': round(min_dist * 111320, 4) if min_dist != float('inf') else '',  # 대략 m 단위
            **{k: props.get(k, '') for k in props if k != 'grid_gid'}
        }
        results.append(row)

    # 5. link_id별 total 계산, link_id로 묶어서 정렬
    link_counts = Counter(r['link_id'] for r in results)
    for r in results:
        r['total'] = link_counts[r['link_id']]
    results.sort(key=lambda r: (r['link_id'], r.get('acc_yr', ''), r.get('acc_mon', '')))

    # 6. 결과 저장 (lon, lat, link_id, total, distance_m + 기타 속성)
    if results:
        cols = ['lon', 'lat', 'link_id', 'total', 'distance_m'] + [
            k for k in results[0] if k not in ('lon', 'lat', 'link_id', 'total', 'distance_m')
        ]
        with open(OUTPUT_ACCIDENT_LINK, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
            w.writeheader()
            w.writerows(results)
        print(f"\n[4] 저장: {OUTPUT_ACCIDENT_LINK}")
        print(f"    교통사고 {len(results)}건 ↔ 링크 정확 매핑 완료")

    print("\n" + "=" * 60)


if __name__ == '__main__':
    main()
