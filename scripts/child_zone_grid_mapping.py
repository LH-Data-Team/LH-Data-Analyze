"""
어린이보호구역 데이터를 격자에 매핑하는 스크립트
- 입력: 01._격자_(4개_시·구).geojson, 14._어린이보호구역.csv
- 출력: output/어린이보호구역_격자매핑.csv
"""

import json
import os
import csv
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

# 파일 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
GRID_FILE = os.path.join(DATA_DIR, '01._격자_(4개_시·구).geojson')
CHILD_ZONE_FILE = os.path.join(DATA_DIR, '14._어린이보호구역.csv')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, '14._어린이보호구역_격자매핑.csv')
ROAD_NETWORK_FILE = os.path.join(DATA_DIR, '08.상세도로망_네트워크.geojson')


def load_geojson(file_path):
    """GeoJSON 파일 로드"""
    print(f"파일 로드 중: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_csv(file_path):
    """CSV 파일 로드"""
    print(f"파일 로드 중: {file_path}")
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data


def save_csv(data, fieldnames, file_path):
    """CSV 파일 저장"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"저장 완료: {file_path}")


def create_grid_index(grid_data):
    """격자 데이터로 R-tree 공간 인덱스 생성"""
    print("격자 인덱스 생성 중...")
    
    polygons = []
    gid_list = []
    
    for feature in grid_data['features']:
        polygon = shape(feature['geometry'])
        gid = feature['properties']['gid']
        polygons.append(polygon)
        gid_list.append(gid)
    
    tree = STRtree(polygons)
    print(f"격자 개수: {len(polygons):,}개")
    
    return tree, polygons, gid_list


def create_link_index(road_data):
    """도로망 link_id R-tree 인덱스 생성"""
    print("도로 링크 인덱스 생성 중...")
    lines = []
    link_ids = []
    for feature in road_data['features']:
        try:
            lines.append(shape(feature['geometry']))
            link_ids.append(feature['properties']['link_id'])
        except Exception:
            continue
    tree = STRtree(lines)
    print(f"도로 링크 개수: {len(link_ids):,}개")
    return tree, link_ids


def find_nearest_link(point, link_tree, link_ids):
    """가장 가까운 도로 링크 link_id 반환"""
    idx = link_tree.nearest(point)
    if idx is not None:
        return link_ids[idx]
    return ''


def map_data_to_grid(data, tree, polygons, gid_list, link_tree, link_ids):
    """데이터 지점을 격자에 매핑"""
    print("어린이보호구역 데이터 격자 매핑 중...")
    
    total = len(data)
    mapped_count = 0
    unmapped_count = 0
    
    for i, row in enumerate(data):
        lon = float(row['lon'])
        lat = float(row['lat'])
        point = Point(lon, lat)
        
        # R-tree로 후보 격자 인덱스 검색
        candidate_indices = tree.query(point)
        matched_gid = None
        
        for idx in candidate_indices:
            if polygons[idx].contains(point):
                matched_gid = gid_list[idx]
                break
        
        # 매핑 결과 저장
        row['grid_gid'] = matched_gid if matched_gid else ''
        row['link_id'] = find_nearest_link(point, link_tree, link_ids)

        if matched_gid:
            mapped_count += 1
        else:
            unmapped_count += 1

        # 진행 상황 출력 (20% 단위)
        if total >= 5 and (i + 1) % (total // 5 + 1) == 0:
            progress = (i + 1) / total * 100
            print(f"  진행률: {progress:.0f}% ({i + 1:,}/{total:,})")

    print(f"\n매핑 완료:")
    print(f"  - 매핑 성공: {mapped_count:,}건")
    print(f"  - 매핑 실패: {unmapped_count:,}건")

    return data


def main():
    print("=" * 50)
    print("어린이보호구역 격자 매핑 시작")
    print("=" * 50)
    
    # 1. 데이터 로드
    grid_data = load_geojson(GRID_FILE)
    road_data = load_geojson(ROAD_NETWORK_FILE)
    child_zone_data = load_csv(CHILD_ZONE_FILE)

    print(f"어린이보호구역 개수: {len(child_zone_data):,}개\n")

    # 2. 격자 인덱스 생성
    tree, polygons, gid_list = create_grid_index(grid_data)

    # 3. 도로 링크 인덱스 생성
    link_tree, link_ids = create_link_index(road_data)

    # 4. 매핑 수행
    result = map_data_to_grid(child_zone_data, tree, polygons, gid_list, link_tree, link_ids)
    
    # 5. 결과 저장
    fieldnames = list(result[0].keys())
    save_csv(result, fieldnames, OUTPUT_FILE)
    
    print("\n" + "=" * 50)
    print("작업 완료!")
    print("=" * 50)


if __name__ == '__main__':
    main()
