"""
과속방지턱 현황 데이터를 격자에 매핑하는 스크립트
- 입력: 01._격자_(4개_시·구).geojson, 21._과속방지턱_현황.csv
- 출력: output/21._과속방지턱_격자매핑.csv
- fac_hght(높이)를 nan/평균이하/평균초과로 분류
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
SPEEDBUMP_FILE = os.path.join(DATA_DIR, '21._과속방지턱_현황.csv')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, '21._과속방지턱_격자매핑.csv')


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


def calculate_height_avg(data):
    """fac_hght의 nan 제외 평균 계산"""
    heights = []
    for row in data:
        hght = row.get('fac_hght', '').strip()
        if hght:
            try:
                heights.append(float(hght))
            except ValueError:
                pass
    
    if heights:
        avg = sum(heights) / len(heights)
        print(f"fac_hght 평균: {avg:.2f} (유효 데이터: {len(heights):,}개)")
        return avg
    return 0


def classify_height(value, avg):
    """높이를 nan/평균이하/평균초과로 분류"""
    if not value or not value.strip():
        return 'nan'
    try:
        hght = float(value)
        if hght <= avg:
            return '평균이하'
        else:
            return '평균초과'
    except ValueError:
        return 'nan'


def map_data_to_grid(data, tree, polygons, gid_list, height_avg):
    """데이터 지점을 격자에 매핑하고 높이 분류 추가"""
    print("과속방지턱 데이터 격자 매핑 중...")
    
    total = len(data)
    mapped_count = 0
    unmapped_count = 0
    
    for i, row in enumerate(data):
        # 높이 분류 추가
        row['hght_class'] = classify_height(row.get('fac_hght', ''), height_avg)
        
        # 좌표가 없으면 스킵
        lon_str = row.get('lon', '').strip()
        lat_str = row.get('lat', '').strip()
        
        if not lon_str or not lat_str:
            row['grid_gid'] = ''
            unmapped_count += 1
            continue
        
        try:
            lon = float(lon_str)
            lat = float(lat_str)
        except ValueError:
            row['grid_gid'] = ''
            unmapped_count += 1
            continue
        
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
        
        # 진행 상황 출력 (10% 단위)
        if (i + 1) % (total // 10 + 1) == 0:
            progress = (i + 1) / total * 100
            print(f"  진행률: {progress:.0f}% ({i + 1:,}/{total:,})")
    
    print(f"\n매핑 완료:")
    print(f"  - 매핑 성공: {mapped_count:,}건")
    print(f"  - 매핑 실패: {unmapped_count:,}건")
    
    return data


def main():
    print("=" * 50)
    print("과속방지턱 현황 격자 매핑 시작")
    print("=" * 50)
    
    # 1. 데이터 로드
    grid_data = load_geojson(GRID_FILE)
    speedbump_data = load_csv(SPEEDBUMP_FILE)
    
    print(f"과속방지턱 개수: {len(speedbump_data):,}개\n")
    
    # 2. fac_hght 평균 계산 (nan 제외)
    height_avg = calculate_height_avg(speedbump_data)
    
    # 3. 격자 인덱스 생성
    tree, polygons, gid_list = create_grid_index(grid_data)
    
    # 4. 매핑 수행 및 높이 분류 추가
    result = map_data_to_grid(speedbump_data, tree, polygons, gid_list, height_avg)
    
    # 5. 높이 분류 통계 출력
    hght_stats = {'nan': 0, '평균이하': 0, '평균초과': 0}
    for row in result:
        hght_class = row.get('hght_class', 'nan')
        hght_stats[hght_class] = hght_stats.get(hght_class, 0) + 1
    
    print(f"\n높이 분류 결과:")
    for k, v in hght_stats.items():
        print(f"  - {k}: {v:,}건")
    
    # 6. 결과 저장
    fieldnames = list(result[0].keys())
    save_csv(result, fieldnames, OUTPUT_FILE)
    
    print("\n" + "=" * 50)
    print("작업 완료!")
    print("=" * 50)


if __name__ == '__main__':
    main()
