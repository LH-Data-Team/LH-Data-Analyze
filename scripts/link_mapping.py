"""
8번 도로망 link_id와 9,10,11,12번 v_link_id 매핑 스크립트
- 8번: up_v_link, dw_v_link → link_id
- 9,10,11,12번: v_link_id 기준으로 link_id 매핑
- link_id ↔ 격자(gid) 매핑: 링크 중심점이 포함된 격자
- 출력: output/09~12번 링크매핑.csv, 08._도로망_link_격자매핑.csv
"""

import json
import os
import csv
from shapely.geometry import shape
from shapely.strtree import STRtree

# 파일 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

GRID_FILE = os.path.join(DATA_DIR, '01._격자_(4개_시·구).geojson')
ROAD_NETWORK_FILE = os.path.join(DATA_DIR, '08.상세도로망_네트워크.geojson')
SPEED_FILE = os.path.join(DATA_DIR, '09._평균속도.csv')
TRAFFIC_FILE = os.path.join(DATA_DIR, '10._추정교통량.csv')
CONGESTION_FILE = os.path.join(DATA_DIR, '11._혼잡빈도강도.csv')
CONGESTION_TIME_FILE = os.path.join(DATA_DIR, '12._혼잡시간강도.csv')

OUTPUT_SPEED = os.path.join(OUTPUT_DIR, '09._평균속도_링크매핑.csv')
OUTPUT_TRAFFIC = os.path.join(OUTPUT_DIR, '10._추정교통량_링크매핑.csv')
OUTPUT_CONGESTION = os.path.join(OUTPUT_DIR, '11._혼잡빈도강도_링크매핑.csv')
OUTPUT_CONGESTION_TIME = os.path.join(OUTPUT_DIR, '12._혼잡시간강도_링크매핑.csv')
OUTPUT_LINK_GRID = os.path.join(OUTPUT_DIR, '08._도로망_link_격자매핑.csv')


def load_geojson(file_path):
    """GeoJSON 파일 로드"""
    print(f"파일 로드 중: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_csv(file_path):
    """CSV 파일 로드"""
    print(f"파일 로드 중: {file_path}")
    data = []
    with open(file_path, 'r', encoding='utf-8-sig') as f:
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


def build_vlink_to_link_map(road_data):
    """8번 도로망에서 v_link_id -> link_id 매핑 테이블 생성"""
    vlink_to_link = {}
    
    for feature in road_data['features']:
        props = feature['properties']
        link_id = props.get('link_id')
        up_v_link = props.get('up_v_link')
        dw_v_link = props.get('dw_v_link')
        
        if link_id is not None:
            if up_v_link and up_v_link != 0:
                vlink_to_link[str(up_v_link)] = link_id
                vlink_to_link[int(up_v_link)] = link_id
            if dw_v_link and dw_v_link != 0:
                vlink_to_link[str(dw_v_link)] = link_id
                vlink_to_link[int(dw_v_link)] = link_id
    
    print(f"v_link_id 매핑 개수: {len(set(str(k) for k in vlink_to_link.keys() if isinstance(k, int))):,}개")
    return vlink_to_link


def create_grid_index(grid_data):
    """격자 데이터로 R-tree 공간 인덱스 생성"""
    polygons = []
    gid_list = []
    for feature in grid_data['features']:
        polygon = shape(feature['geometry'])
        gid = feature['properties']['gid']
        polygons.append(polygon)
        gid_list.append(gid)
    tree = STRtree(polygons)
    return tree, polygons, gid_list


def build_link_to_grid_map(road_data, tree, polygons, gid_list):
    """8번 도로망 link_id → 격자(gid) 매핑 (링크 중심점 기준)"""
    result = []
    mapped = 0
    unmapped = 0
    
    for i, feature in enumerate(road_data['features']):
        link_id = feature['properties'].get('link_id')
        try:
            line = shape(feature['geometry'])
            centroid = line.centroid
        except Exception:
            result.append({'link_id': link_id, 'grid_gid': ''})
            unmapped += 1
            continue
        
        candidate_indices = tree.query(centroid)
        matched_gid = None
        for idx in candidate_indices:
            if polygons[idx].contains(centroid):
                matched_gid = gid_list[idx]
                break
        
        result.append({'link_id': link_id, 'grid_gid': matched_gid or ''})
        if matched_gid:
            mapped += 1
        else:
            unmapped += 1
        
        if (i + 1) % 1000 == 0:
            print(f"  진행: {i + 1:,}/{len(road_data['features']):,}")
    
    print(f"  link_id→격자 매핑: 성공 {mapped:,}건, 실패 {unmapped:,}건")
    return result


def map_csv_with_link_id(data, vlink_map, file_name):
    """CSV 데이터에 link_id 매핑 추가"""
    mapped = 0
    unmapped = 0
    
    for row in data:
        v_link_id = row.get('v_link_id', '').strip()
        link_id = vlink_map.get(v_link_id) or vlink_map.get(int(v_link_id)) if v_link_id else None
        row['link_id'] = link_id if link_id is not None else ''
        
        if row['link_id']:
            mapped += 1
        else:
            unmapped += 1
    
    print(f"  {file_name}: 매핑 성공 {mapped:,}건, 실패 {unmapped:,}건")
    return data


def main():
    print("=" * 60)
    print("8번 link_id ↔ 9,10,11,12번 v_link_id 매핑")
    print("=" * 60)
    
    # 1. 8번 도로망 로드 및 v_link -> link 매핑 테이블 생성
    road_data = load_geojson(ROAD_NETWORK_FILE)
    vlink_map = build_vlink_to_link_map(road_data)
    
    # 1-1. link_id ↔ 격자 매핑
    print("\n[link_id↔격자] 도로망 링크 격자 매핑...")
    grid_data = load_geojson(GRID_FILE)
    tree, polygons, gid_list = create_grid_index(grid_data)
    link_grid_map = build_link_to_grid_map(road_data, tree, polygons, gid_list)
    save_csv(link_grid_map, ['link_id', 'grid_gid'], OUTPUT_LINK_GRID)
    
    # 2. 9번 평균속도 매핑
    print("\n[9번] 평균속도 매핑...")
    speed_data = load_csv(SPEED_FILE)
    speed_mapped = map_csv_with_link_id(speed_data, vlink_map, "09._평균속도")
    fieldnames_speed = ['v_link_id', 'link_id'] + [c for c in speed_mapped[0].keys() if c not in ('v_link_id', 'link_id')]
    save_csv(speed_mapped, fieldnames_speed, OUTPUT_SPEED)
    
    # 3. 10번 추정교통량 매핑
    print("\n[10번] 추정교통량 매핑...")
    traffic_data = load_csv(TRAFFIC_FILE)
    traffic_mapped = map_csv_with_link_id(traffic_data, vlink_map, "10._추정교통량")
    fieldnames_traffic = ['v_link_id', 'link_id'] + [c for c in traffic_mapped[0].keys() if c not in ('v_link_id', 'link_id')]
    save_csv(traffic_mapped, fieldnames_traffic, OUTPUT_TRAFFIC)
    
    # 4. 11번 혼잡빈도강도 매핑
    print("\n[11번] 혼잡빈도강도 매핑...")
    congestion_data = load_csv(CONGESTION_FILE)
    congestion_mapped = map_csv_with_link_id(congestion_data, vlink_map, "11._혼잡빈도강도")
    fieldnames_congestion = ['v_link_id', 'link_id'] + [c for c in congestion_mapped[0].keys() if c not in ('v_link_id', 'link_id')]
    save_csv(congestion_mapped, fieldnames_congestion, OUTPUT_CONGESTION)
    
    # 5. 12번 혼잡시간강도 매핑
    print("\n[12번] 혼잡시간강도 매핑...")
    congestion_time_data = load_csv(CONGESTION_TIME_FILE)
    congestion_time_mapped = map_csv_with_link_id(congestion_time_data, vlink_map, "12._혼잡시간강도")
    fieldnames_congestion_time = ['v_link_id', 'link_id'] + [c for c in congestion_time_mapped[0].keys() if c not in ('v_link_id', 'link_id')]
    save_csv(congestion_time_mapped, fieldnames_congestion_time, OUTPUT_CONGESTION_TIME)
    
    print("\n" + "=" * 60)
    print("작업 완료!")
    print("=" * 60)


if __name__ == '__main__':
    main()
