"""
08._도로망_link_격자매핑.csv에 격자별 accident_cnt 매핑
- accident_cnt 높은 순, 동일하면 grid_gid순 정렬
"""

import os
import csv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
LINK_GRID_FILE = os.path.join(OUTPUT_DIR, '08._도로망_link_격자매핑.csv')
GRID_DATA_FILE = os.path.join(OUTPUT_DIR, '격자별_통합데이터.csv')


def main():
    # 격자별 accident_cnt 로드
    grid_accident = {}
    with open(GRID_DATA_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            gid = row.get('grid_gid', '')
            cnt = row.get('accident_cnt', '0')
            grid_accident[gid] = cnt

    # 08 파일 로드 및 accident_cnt 추가
    rows = []
    with open(LINK_GRID_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        if 'accident_cnt' not in fieldnames:
            fieldnames.append('accident_cnt')
        for row in reader:
            gid = row.get('grid_gid', '')
            if 'accident_cnt' not in row:
                row['accident_cnt'] = grid_accident.get(gid, '0')
            rows.append(row)

    # accident_cnt 높은 순, 동일하면 grid_gid순 정렬
    rows.sort(key=lambda r: (-int(r.get('accident_cnt', 0) or 0), r.get('grid_gid', '')))

    with open(LINK_GRID_FILE, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    print(f"완료: {LINK_GRID_FILE} (accident_cnt 높은순, grid_gid순 정렬)")


if __name__ == '__main__':
    main()
