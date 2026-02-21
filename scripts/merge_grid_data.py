"""
격자 기준으로 7개 매핑 결과를 하나의 파일로 합치는 스크립트
- 입력: output 폴더의 7개 매핑 파일
- 출력: output/격자별_통합데이터.csv
"""

import json
import os
import csv
from collections import defaultdict

# 파일 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
GRID_FILE = os.path.join(DATA_DIR, '01._격자_(4개_시·구).geojson')

# 입력 파일들
ACCIDENT_FILE = os.path.join(OUTPUT_DIR, '13._교통사고_격자매핑.geojson')
CROSSWALK_FILE = os.path.join(OUTPUT_DIR, '18._횡단보도_격자매핑.csv')
CHILD_ZONE_FILE = os.path.join(OUTPUT_DIR, '14._어린이보호구역_격자매핑.csv')
KINDERGARTEN_FILE = os.path.join(OUTPUT_DIR, '16._유치원현황_격자매핑.csv')
DAYCARE_FILE = os.path.join(OUTPUT_DIR, '17._어린이집현황_격자매핑.csv')
CCTV_FILE = os.path.join(OUTPUT_DIR, '20._CCTV현황_격자매핑.csv')
SPEEDBUMP_FILE = os.path.join(OUTPUT_DIR, '21._과속방지턱_격자매핑.csv')

# 출력 파일
OUTPUT_FILE = os.path.join(OUTPUT_DIR, '격자별_통합데이터.csv')


def load_geojson(file_path):
    """GeoJSON 파일 로드"""
    print(f"파일 로드 중: {os.path.basename(file_path)}")
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_csv(file_path):
    """CSV 파일 로드"""
    print(f"파일 로드 중: {os.path.basename(file_path)}")
    data = []
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data


def save_csv(data, fieldnames, file_path):
    """CSV 파일 저장"""
    with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"저장 완료: {file_path}")


def main():
    print("=" * 60)
    print("격자별 통합 데이터 생성 시작")
    print("=" * 60)
    
    # 격자별 데이터 저장용 딕셔너리
    grid_data = defaultdict(lambda: {
        'accident_cnt': 0,           # 교통사고 건수
        'crosswalk_cnt': 0,          # 횡단보도 개수
        'child_zone_cnt': 0,         # 어린이보호구역 개수
        'kindergarten_cnt': 0,       # 유치원 개수
        'kindergarten_child_cnt': 0, # 유치원 원아수 (3~5세 합계)
        'daycare_cnt': 0,            # 어린이집 개수 (정상만)
        'cctv_cnt': 0,               # CCTV 설치 개수
        'cctv_cam_cnt': 0,           # CCTV 카메라 총 대수
        'speedbump_cnt': 0,          # 과속방지턱 총 개수
        'speedbump_hght_nan': 0,     # 과속방지턱 높이 nan
        'speedbump_hght_below': 0,   # 과속방지턱 높이 평균이하
        'speedbump_hght_above': 0,   # 과속방지턱 높이 평균초과
    })
    
    # 1. 교통사고 데이터 집계
    print("\n[1/7] 교통사고 데이터 집계 중...")
    accident_data = load_geojson(ACCIDENT_FILE)
    for feature in accident_data['features']:
        gid = feature['properties'].get('grid_gid')
        if gid:
            grid_data[gid]['accident_cnt'] += 1
    print(f"  - 총 {len([f for f in accident_data['features'] if f['properties'].get('grid_gid')]):,}건 집계")
    
    # 2. 횡단보도 데이터 집계
    print("\n[2/7] 횡단보도 데이터 집계 중...")
    crosswalk_data = load_csv(CROSSWALK_FILE)
    for row in crosswalk_data:
        gid = row.get('grid_gid')
        if gid:
            grid_data[gid]['crosswalk_cnt'] += 1
    print(f"  - 총 {len([r for r in crosswalk_data if r.get('grid_gid')]):,}건 집계")
    
    # 3. 어린이보호구역 데이터 집계
    print("\n[3/7] 어린이보호구역 데이터 집계 중...")
    child_zone_data = load_csv(CHILD_ZONE_FILE)
    for row in child_zone_data:
        gid = row.get('grid_gid')
        if gid:
            grid_data[gid]['child_zone_cnt'] += 1
    print(f"  - 총 {len([r for r in child_zone_data if r.get('grid_gid')]):,}건 집계")
    
    # 4. 유치원 데이터 집계
    print("\n[4/7] 유치원 데이터 집계 중...")
    kindergarten_data = load_csv(KINDERGARTEN_FILE)
    for row in kindergarten_data:
        gid = row.get('grid_gid')
        if gid:
            grid_data[gid]['kindergarten_cnt'] += 1
            # 원아수 합계
            child_cnt = int(row.get('total_age_cnt', 0) or 0)
            grid_data[gid]['kindergarten_child_cnt'] += child_cnt
    print(f"  - 총 {len([r for r in kindergarten_data if r.get('grid_gid')]):,}건 집계")
    
    # 5. 어린이집 데이터 집계 (정상인 것만)
    print("\n[5/7] 어린이집 데이터 집계 중 (정상만)...")
    daycare_data = load_csv(DAYCARE_FILE)
    normal_cnt = 0
    for row in daycare_data:
        gid = row.get('grid_gid')
        if gid and row.get('oper_stat') == '정상':
            grid_data[gid]['daycare_cnt'] += 1
            normal_cnt += 1
    print(f"  - 총 {normal_cnt:,}건 집계 (정상 운영)")
    
    # 6. CCTV 데이터 집계
    print("\n[6/7] CCTV 데이터 집계 중...")
    cctv_data = load_csv(CCTV_FILE)
    for row in cctv_data:
        gid = row.get('grid_gid')
        if gid:
            grid_data[gid]['cctv_cnt'] += 1
            cam_cnt = int(row.get('cam_cnt', 0) or 0)
            grid_data[gid]['cctv_cam_cnt'] += cam_cnt
    print(f"  - 총 {len([r for r in cctv_data if r.get('grid_gid')]):,}건 집계")
    
    # 7. 과속방지턱 데이터 집계
    print("\n[7/7] 과속방지턱 데이터 집계 중...")
    speedbump_data = load_csv(SPEEDBUMP_FILE)
    for row in speedbump_data:
        gid = row.get('grid_gid')
        if gid:
            grid_data[gid]['speedbump_cnt'] += 1
            hght_class = row.get('hght_class', 'nan')
            if hght_class == 'nan':
                grid_data[gid]['speedbump_hght_nan'] += 1
            elif hght_class == '평균이하':
                grid_data[gid]['speedbump_hght_below'] += 1
            elif hght_class == '평균초과':
                grid_data[gid]['speedbump_hght_above'] += 1
    print(f"  - 총 {len([r for r in speedbump_data if r.get('grid_gid')]):,}건 집계")
    
    # 결과 정리
    print("\n" + "=" * 60)
    print("결과 정리 중...")
    
    # 모든 격자 정보 로드 (매핑된 격자만 포함하려면 grid_data.keys() 사용)
    result = []
    for gid in sorted(grid_data.keys()):
        row = {
            'grid_gid': gid,
            'accident_cnt': grid_data[gid]['accident_cnt'],
            'crosswalk_cnt': grid_data[gid]['crosswalk_cnt'],
            'child_zone_cnt': grid_data[gid]['child_zone_cnt'],
            'kindergarten_cnt': grid_data[gid]['kindergarten_cnt'],
            'kindergarten_child_cnt': grid_data[gid]['kindergarten_child_cnt'],
            'daycare_cnt': grid_data[gid]['daycare_cnt'],
            'cctv_cnt': grid_data[gid]['cctv_cnt'],
            'cctv_cam_cnt': grid_data[gid]['cctv_cam_cnt'],
            'speedbump_cnt': grid_data[gid]['speedbump_cnt'],
            'speedbump_hght_nan': grid_data[gid]['speedbump_hght_nan'],
            'speedbump_hght_below': grid_data[gid]['speedbump_hght_below'],
            'speedbump_hght_above': grid_data[gid]['speedbump_hght_above'],
        }
        result.append(row)
    
    # 저장
    fieldnames = [
        'grid_gid',
        'accident_cnt',
        'crosswalk_cnt', 
        'child_zone_cnt',
        'kindergarten_cnt',
        'kindergarten_child_cnt',
        'daycare_cnt',
        'cctv_cnt',
        'cctv_cam_cnt',
        'speedbump_cnt',
        'speedbump_hght_nan',
        'speedbump_hght_below',
        'speedbump_hght_above'
    ]
    save_csv(result, fieldnames, OUTPUT_FILE)
    
    # 통계 출력
    print("\n" + "=" * 60)
    print("통합 결과 요약")
    print("=" * 60)
    print(f"총 격자 수: {len(result):,}개")
    print(f"\n컬럼별 합계:")
    print(f"  - 교통사고 건수: {sum(r['accident_cnt'] for r in result):,}건")
    print(f"  - 횡단보도 개수: {sum(r['crosswalk_cnt'] for r in result):,}개")
    print(f"  - 어린이보호구역: {sum(r['child_zone_cnt'] for r in result):,}개")
    print(f"  - 유치원 개수: {sum(r['kindergarten_cnt'] for r in result):,}개")
    print(f"  - 유치원 원아수: {sum(r['kindergarten_child_cnt'] for r in result):,}명")
    print(f"  - 어린이집 개수: {sum(r['daycare_cnt'] for r in result):,}개")
    print(f"  - CCTV 설치 개수: {sum(r['cctv_cnt'] for r in result):,}개")
    print(f"  - CCTV 카메라 수: {sum(r['cctv_cam_cnt'] for r in result):,}대")
    print(f"  - 과속방지턱 개수: {sum(r['speedbump_cnt'] for r in result):,}개")
    print(f"    └ 높이 nan: {sum(r['speedbump_hght_nan'] for r in result):,}개")
    print(f"    └ 높이 평균이하: {sum(r['speedbump_hght_below'] for r in result):,}개")
    print(f"    └ 높이 평균초과: {sum(r['speedbump_hght_above'] for r in result):,}개")
    
    print("\n" + "=" * 60)
    print("작업 완료!")
    print("=" * 60)


if __name__ == '__main__':
    main()
