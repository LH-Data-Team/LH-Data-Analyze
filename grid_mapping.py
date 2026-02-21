"""
교통사고 이력 데이터를 격자에 매핑하는 스크립트
- 입력: 01._격자_(4개_시·구).geojson, 13._교통사고이력.geojson
- 출력: output/교통사고_격자매핑.geojson
"""

import json
import os
from shapely.geometry import shape
from shapely.strtree import STRtree

# 파일 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GRID_FILE = os.path.join(BASE_DIR, '01._격자_(4개_시·구).geojson')
ACCIDENT_FILE = os.path.join(BASE_DIR, '13._교통사고이력.geojson')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, '교통사고_격자매핑.geojson')


def load_geojson(file_path):
    """GeoJSON 파일 로드"""
    print(f"파일 로드 중: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_geojson(data, file_path):
    """GeoJSON 파일 저장"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
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


def map_accidents_to_grid(accident_data, tree, polygons, gid_list):
    """교통사고 지점을 격자에 매핑"""
    print("교통사고 데이터 격자 매핑 중...")
    
    total = len(accident_data['features'])
    mapped_count = 0
    unmapped_count = 0
    
    for i, accident in enumerate(accident_data['features']):
        point = shape(accident['geometry'])
        
        # R-tree로 후보 격자 인덱스 검색 (shapely 2.x)
        candidate_indices = tree.query(point)
        matched_gid = None
        
        for idx in candidate_indices:
            if polygons[idx].contains(point):
                matched_gid = gid_list[idx]
                break
        
        # 매핑 결과 저장
        accident['properties']['grid_gid'] = matched_gid
        
        if matched_gid:
            mapped_count += 1
        else:
            unmapped_count += 1
        
        # 진행 상황 출력 (10% 단위)
        if (i + 1) % (total // 10 + 1) == 0:
            progress = (i + 1) / total * 100
            print(f"  진행률: {progress:.0f}% ({i + 1:,}/{total:,})")
    
    print(f"\n매핑 완료:")
    print(f"  - 매핑 성공: {mapped_count:,}건")
    print(f"  - 매핑 실패: {unmapped_count:,}건")
    
    return accident_data


def main():
    print("=" * 50)
    print("교통사고 이력 격자 매핑 시작")
    print("=" * 50)
    
    # 1. 데이터 로드
    grid_data = load_geojson(GRID_FILE)
    accident_data = load_geojson(ACCIDENT_FILE)
    
    print(f"교통사고 건수: {len(accident_data['features']):,}건\n")
    
    # 2. 격자 인덱스 생성
    tree, polygons, gid_list = create_grid_index(grid_data)
    
    # 3. 매핑 수행
    result = map_accidents_to_grid(accident_data, tree, polygons, gid_list)
    
    # 4. 결과 저장
    output_data = {
        "type": "FeatureCollection",
        "name": "교통사고_격자매핑",
        "crs": accident_data.get('crs'),
        "features": result['features']
    }
    
    save_geojson(output_data, OUTPUT_FILE)
    
    print("\n" + "=" * 50)
    print("작업 완료!")
    print("=" * 50)


if __name__ == '__main__':
    main()
