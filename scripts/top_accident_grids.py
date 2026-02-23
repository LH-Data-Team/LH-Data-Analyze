"""
사고 다발 격자 상위 50개 분석 스크립트
- 입력: output 폴더의 매핑 파일들
- 출력: output/사고다발_상위50_격자.json (모든 상세 데이터 포함)
"""

import os
import csv
import json

# 파일 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

# 입력 파일들
INTEGRATED_FILE = os.path.join(OUTPUT_DIR, '격자별_통합데이터.csv')
ACCIDENT_FILE = os.path.join(OUTPUT_DIR, '13._교통사고_격자매핑.geojson')
CROSSWALK_FILE = os.path.join(OUTPUT_DIR, '18._횡단보도_격자매핑.csv')
CHILD_ZONE_FILE = os.path.join(OUTPUT_DIR, '14._어린이보호구역_격자매핑.csv')
KINDERGARTEN_FILE = os.path.join(OUTPUT_DIR, '16._유치원현황_격자매핑.csv')
DAYCARE_FILE = os.path.join(OUTPUT_DIR, '17._어린이집현황_격자매핑.csv')
CCTV_FILE = os.path.join(OUTPUT_DIR, '20._CCTV현황_격자매핑.csv')
SPEEDBUMP_FILE = os.path.join(OUTPUT_DIR, '21._과속방지턱_격자매핑.csv')

# 출력 파일
OUTPUT_FILE = os.path.join(OUTPUT_DIR, '사고다발_상위50_격자.json')


def load_csv(file_path):
    """CSV 파일 로드"""
    print(f"파일 로드 중: {os.path.basename(file_path)}")
    data = []
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data


def load_geojson(file_path):
    """GeoJSON 파일 로드"""
    print(f"파일 로드 중: {os.path.basename(file_path)}")
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_data_by_grid(data, grid_gids, gid_key='grid_gid'):
    """특정 격자들에 해당하는 데이터만 추출"""
    result = {gid: [] for gid in grid_gids}
    for row in data:
        gid = row.get(gid_key)
        if gid in result:
            result[gid].append(row)
    return result


def get_accident_by_grid(geojson_data, grid_gids):
    """GeoJSON에서 특정 격자들에 해당하는 사고 데이터 추출"""
    result = {gid: [] for gid in grid_gids}
    for feature in geojson_data['features']:
        gid = feature['properties'].get('grid_gid')
        if gid in result:
            # properties와 coordinates 모두 포함
            accident_info = feature['properties'].copy()
            accident_info['coordinates'] = feature['geometry']['coordinates']
            result[gid].append(accident_info)
    return result


def main():
    print("=" * 60)
    print("사고 다발 격자 상위 50개 상세 분석")
    print("=" * 60)
    
    # 1. 통합 데이터 로드 및 상위 50개 추출
    integrated_data = load_csv(INTEGRATED_FILE)
    sorted_data = sorted(integrated_data, key=lambda x: int(x['accident_cnt']), reverse=True)
    top_50 = sorted_data[:50]
    top_50_gids = [row['grid_gid'] for row in top_50]
    
    print(f"\n상위 50개 격자 추출 완료")
    print(f"  - 1위: {top_50[0]['grid_gid']} (사고 {top_50[0]['accident_cnt']}건)")
    print(f"  - 50위: {top_50[-1]['grid_gid']} (사고 {top_50[-1]['accident_cnt']}건)")
    
    # 2. 각 데이터 파일에서 해당 격자 데이터 추출
    print("\n" + "-" * 40)
    
    # 교통사고 데이터
    accident_geojson = load_geojson(ACCIDENT_FILE)
    accidents_by_grid = get_accident_by_grid(accident_geojson, top_50_gids)
    
    # 횡단보도 데이터
    crosswalk_data = load_csv(CROSSWALK_FILE)
    crosswalks_by_grid = get_data_by_grid(crosswalk_data, top_50_gids)
    
    # 어린이보호구역 데이터
    child_zone_data = load_csv(CHILD_ZONE_FILE)
    child_zones_by_grid = get_data_by_grid(child_zone_data, top_50_gids)
    
    # 유치원 데이터
    kindergarten_data = load_csv(KINDERGARTEN_FILE)
    kindergartens_by_grid = get_data_by_grid(kindergarten_data, top_50_gids)
    
    # 어린이집 데이터
    daycare_data = load_csv(DAYCARE_FILE)
    daycares_by_grid = get_data_by_grid(daycare_data, top_50_gids)
    
    # CCTV 데이터
    cctv_data = load_csv(CCTV_FILE)
    cctvs_by_grid = get_data_by_grid(cctv_data, top_50_gids)
    
    # 과속방지턱 데이터
    speedbump_data = load_csv(SPEEDBUMP_FILE)
    speedbumps_by_grid = get_data_by_grid(speedbump_data, top_50_gids)
    
    # 3. 결과 JSON 구성
    print("\n" + "-" * 40)
    print("JSON 데이터 구성 중...")
    
    result = []
    for i, row in enumerate(top_50, 1):
        gid = row['grid_gid']
        
        grid_info = {
            'rank': i,
            'grid_gid': gid,
            'summary': {
                'accident_cnt': int(row['accident_cnt']),
                'crosswalk_cnt': int(row['crosswalk_cnt']),
                'child_zone_cnt': int(row['child_zone_cnt']),
                'kindergarten_cnt': int(row['kindergarten_cnt']),
                'kindergarten_child_cnt': int(row['kindergarten_child_cnt']),
                'daycare_cnt': int(row['daycare_cnt']),
                'cctv_cnt': int(row['cctv_cnt']),
                'cctv_cam_cnt': int(row['cctv_cam_cnt']),
                'speedbump_cnt': int(row['speedbump_cnt']),
                'speedbump_hght_nan': int(row['speedbump_hght_nan']),
                'speedbump_hght_below': int(row['speedbump_hght_below']),
                'speedbump_hght_above': int(row['speedbump_hght_above']),
            },
            'accidents': accidents_by_grid.get(gid, []),
            'crosswalks': crosswalks_by_grid.get(gid, []),
            'child_zones': child_zones_by_grid.get(gid, []),
            'kindergartens': kindergartens_by_grid.get(gid, []),
            'daycares': daycares_by_grid.get(gid, []),
            'cctvs': cctvs_by_grid.get(gid, []),
            'speedbumps': speedbumps_by_grid.get(gid, []),
        }
        result.append(grid_info)
    
    # 4. JSON 저장
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"저장 완료: {OUTPUT_FILE}")
    
    # 5. 미리보기 (1위 격자)
    print("\n" + "=" * 60)
    print("1위 격자 미리보기")
    print("=" * 60)
    
    top1 = result[0]
    print(f"\n격자 ID: {top1['grid_gid']}")
    print(f"\n[요약]")
    for k, v in top1['summary'].items():
        if v > 0:
            print(f"  {k}: {v}")
    
    print(f"\n[사고 데이터] ({len(top1['accidents'])}건)")
    for j, acc in enumerate(top1['accidents'][:3], 1):
        print(f"  {j}. {acc.get('acc_type', '')} / {acc.get('violation', '')} / {acc.get('acc_time', '')} / {acc.get('weather', '')}")
    if len(top1['accidents']) > 3:
        print(f"  ... 외 {len(top1['accidents']) - 3}건")
    
    if top1['crosswalks']:
        print(f"\n[횡단보도] ({len(top1['crosswalks'])}개)")
        for j, cw in enumerate(top1['crosswalks'][:2], 1):
            print(f"  {j}. {cw.get('addr', '')[:50]}...")
    
    if top1['cctvs']:
        print(f"\n[CCTV] ({len(top1['cctvs'])}개)")
        for j, cctv in enumerate(top1['cctvs'][:2], 1):
            print(f"  {j}. {cctv.get('addr', '')[:50]}... (카메라 {cctv.get('cam_cnt', 0)}대)")
    
    if top1['speedbumps']:
        print(f"\n[과속방지턱] ({len(top1['speedbumps'])}개)")
        for j, sb in enumerate(top1['speedbumps'][:2], 1):
            print(f"  {j}. {sb.get('addr', '')[:50]}... (높이: {sb.get('fac_hght', 'nan')})")
    
    print("\n" + "=" * 60)
    print("작업 완료!")
    print("=" * 60)


if __name__ == '__main__':
    main()
