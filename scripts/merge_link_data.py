"""
9, 10, 11, 12번 링크 데이터 통합 (격자 제외, 중복 컬럼 제외)
- v_link_id 기준으로 merge
- 격자(gid, grid_gid 등) 컬럼 제외
- 공통 컬럼은 1개만 유지
"""

import os
import csv
from collections import OrderedDict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, '09_10_11_12_링크통합.csv')

EXCLUDE_COLS = {'gid', 'grid_gid', '격자', '격자_id'}


def load_csv(file_path):
    """CSV 로드 (BOM 처리)"""
    rows = []
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k: v for k, v in row.items() if k})
    return rows, list(rows[0].keys()) if rows else []


def main():
    print("=" * 60)
    print("9, 10, 11, 12번 링크 데이터 통합 (격자 제외, 중복 컬럼 제외)")
    print("=" * 60)

    # 1. 9번과 10번 merge (v_link_id + timeslot 기준)
    d9, cols9 = load_csv(os.path.join(DATA_DIR, '09._평균속도.csv'))
    d10, cols10 = load_csv(os.path.join(DATA_DIR, '10._추정교통량.csv'))
    print(f"\n9번: {len(d9):,}행, 10번: {len(d10):,}행")

    key_9_10 = ['v_link_id', 'road_rank', 'k_length', 'sido_id', 'sigungu_id', 'emd_id',
                'sido_name', 'sigungu_name', 'emd_name', 'timeslot']
    only_9 = [c for c in cols9 if c not in cols10]
    only_10 = [c for c in cols10 if c not in cols9]
    common_9_10 = [c for c in key_9_10 if c in cols9]

    idx_10 = {}
    for row in d10:
        k = tuple(row.get(c, '') for c in common_9_10)
        idx_10[k] = row

    keys_9 = {tuple(r.get(c, '') for c in common_9_10) for r in d9}

    merged_9_10 = []
    for row in d9:
        k = tuple(row.get(c, '') for c in common_9_10)
        r = dict(row)
        if k in idx_10:
            for c in only_10:
                r[c] = idx_10[k].get(c, '')
        else:
            for c in only_10:
                r[c] = ''
        merged_9_10.append(r)

    for k, row in idx_10.items():
        if k not in keys_9:
            r = {c: row.get(c, '') for c in common_9_10}
            for c in only_9:
                r[c] = ''
            for c in only_10:
                r[c] = row.get(c, '')
            merged_9_10.append(r)

    cols_9_10 = list(OrderedDict.fromkeys(common_9_10 + only_9 + only_10))
    print(f"9+10 merge: {len(merged_9_10):,}행")

    # 2. 11번 merge
    d11, cols11 = load_csv(os.path.join(DATA_DIR, '11._혼잡빈도강도.csv'))
    print(f"11번: {len(d11):,}행")

    only_11 = [c for c in cols11 if c not in cols_9_10]
    idx_11 = {row['v_link_id']: row for row in d11}

    for row in merged_9_10:
        vid = row.get('v_link_id', '')
        r11 = idx_11.get(vid, {})
        for c in only_11:
            row[c] = r11.get(c, '')
    cols_9_10_11 = cols_9_10 + only_11
    print(f"9+10+11 merge: {len(merged_9_10):,}행")

    # 3. 12번 merge
    d12, cols12 = load_csv(os.path.join(DATA_DIR, '12._혼잡시간강도.csv'))
    print(f"12번: {len(d12):,}행")

    only_12 = [c for c in cols12 if c not in cols_9_10_11]
    idx_12 = {row['v_link_id']: row for row in d12}

    for row in merged_9_10:
        vid = row.get('v_link_id', '')
        r12 = idx_12.get(vid, {})
        for c in only_12:
            row[c] = r12.get(c, '')
    cols_final = cols_9_10_11 + only_12

    # 4. 격자 컬럼 제외
    cols_final = [c for c in cols_final if c not in EXCLUDE_COLS and '격자' not in c]

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols_final, extrasaction='ignore')
        w.writeheader()
        w.writerows(merged_9_10)

    print(f"\n저장 완료: {OUTPUT_FILE}")
    print(f"컬럼: {cols_final}")


if __name__ == '__main__':
    main()
