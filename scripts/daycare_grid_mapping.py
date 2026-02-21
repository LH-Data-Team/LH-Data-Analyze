"""
어린이집현황 데이터를 격자에 매핑하는 스크립트
- 입력: 01._격자_(4개_시·구).geojson, 17._어린이집현황.csv
- 출력: output/어린이집현황_격자매핑.csv
- 조건: oper_stat이 "정상"인 곳만 격자 매핑
- 정렬: 정상 -> 폐지 순서로 배치
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
DAYCARE_FILE = os.path.join(DATA_DIR, '17._어린이집현황.csv')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, '17._어린이집현황_격자매핑.csv')


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


def map_data_to_grid(data, tree, polygons, gid_list):
    """데이터 지점을 격자에 매핑 (oper_stat이 '정상'인 경우만)"""
    print("어린이집 데이터 격자 매핑 중...")
    
    # 정상/폐지 분리
    normal = [row for row in data if row['oper_stat'] == '정상']
    closed = [row for row in data if row['oper_stat'] == '폐지']
    others = [row for row in data if row['oper_stat'] not in ['정상', '폐지']]
    
    print(f"  - 정상: {len(normal):,}개")
    print(f"  - 폐지: {len(closed):,}개")
    print(f"  - 기타: {len(others):,}개")
    
    mapped_count = 0
    unmapped_count = 0
    
    # 정상인 곳만 격자 매핑
    for i, row in enumerate(normal):
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
        
        if matched_gid:
            mapped_count += 1
        else:
            unmapped_count += 1
        
        # 진행 상황 출력 (20% 단위)
        total = len(normal)
        if total >= 5 and (i + 1) % (total // 5 + 1) == 0:
            progress = (i + 1) / total * 100
            print(f"  진행률: {progress:.0f}% ({i + 1:,}/{total:,})")
    
    # 폐지/기타는 grid_gid를 빈 값으로 설정
    for row in closed:
        row['grid_gid'] = ''
    for row in others:
        row['grid_gid'] = ''
    
    print(f"\n매핑 완료 (정상 어린이집만):")
    print(f"  - 매핑 성공: {mapped_count:,}건")
    print(f"  - 매핑 실패: {unmapped_count:,}건")
    
    # 정상 -> 폐지 -> 기타 순서로 합치기
    result = normal + closed + others
    
    return result


def main():
    print("=" * 50)
    print("어린이집현황 격자 매핑 시작")
    print("=" * 50)
    
    # 1. 데이터 로드
    grid_data = load_geojson(GRID_FILE)
    daycare_data = load_csv(DAYCARE_FILE)
    
    print(f"어린이집 총 개수: {len(daycare_data):,}개\n")
    
    # 2. 격자 인덱스 생성
    tree, polygons, gid_list = create_grid_index(grid_data)
    
    # 3. 매핑 수행 (정상인 곳만, 정렬: 정상 -> 폐지 -> 기타)
    result = map_data_to_grid(daycare_data, tree, polygons, gid_list)
    
    # 4. 결과 저장
    fieldnames = list(result[0].keys())
    save_csv(result, fieldnames, OUTPUT_FILE)
    
    print("\n" + "=" * 50)
    print("작업 완료!")
    print("=" * 50)


if __name__ == '__main__':
    main()
