# -*- coding: utf-8 -*-
"""08.상세도로망_네트워크 전처리
- level == '6.0' 필터링 (지표 생성 대상 구간만)
- 분석에 필요한 컬럼만 선택
- 결측치 처리 및 기초 통계 출력
"""

import geopandas as gpd
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
RAW_PATH = os.path.join(PROJECT_DIR, "08.상세도로망_네트워크.geojson")
OUT_PATH = os.path.join(SCRIPT_DIR, "08._상세도로망_네트워크_preprocessed.geojson")

gdf = gpd.read_file(RAW_PATH)
print(f"원본 row: {len(gdf)}")

use_cols = [
    "link_id",
    "up_v_link", "dw_v_link",
    "max_speed",
    "road_rank",
    "road_type",
    "lanes",
    "oneway",
    "length",
    "level",
    "road_name",
    "sido_id", "sigungu_id", "emd_id",
    "geometry",
]
gdf = gdf[use_cols].copy()

# level 6.0만 필터링 (지표 생성 대상 구간)
gdf = gdf[gdf["level"] == "6.0"].reset_index(drop=True)
print(f"level 6.0 필터 후: {len(gdf)}")

# 결측치 확인
null_cnt = gdf.drop(columns="geometry").isnull().sum()
has_null = null_cnt[null_cnt > 0]
if len(has_null) > 0:
    print("\n--- 결측치 ---")
    for col, cnt in has_null.items():
        print(f"  {col}: {cnt}개")

# road_name 결측은 빈 문자열 처리
gdf["road_name"] = gdf["road_name"].fillna("")

# 수치 컬럼 결측 확인 및 음수 클리핑
num_cols = ["max_speed", "lanes", "length"]
gdf[num_cols] = gdf[num_cols].fillna(0)
gdf[num_cols] = gdf[num_cols].clip(lower=0)

# 기초 통계
print(f"\n--- 기초 통계 ---")
print(f"도로 링크 수: {len(gdf)}")
print(f"road_rank 분포:\n{gdf['road_rank'].value_counts().sort_index().to_string()}")
print(f"\nroad_type 분포:\n{gdf['road_type'].value_counts().sort_index().to_string()}")
print(f"\nmax_speed 분포:\n{gdf['max_speed'].describe().to_string()}")
print(f"\nlanes 분포:\n{gdf['lanes'].value_counts().sort_index().to_string()}")
print(f"\noneway 분포:\n{gdf['oneway'].value_counts().to_string()}")

gdf.to_file(OUT_PATH, driver="GeoJSON", encoding="utf-8")
print(f"\n저장 완료: {OUT_PATH}")
