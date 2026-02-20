# -*- coding: utf-8 -*-
"""09._평균속도 전처리
- 08번과 중복되는 컬럼 제거
- v_link_id, timeslot, velocity_AVRG, probe만 유지
- 결측/음수 처리, IQR 이상치 플래그
"""

import pandas as pd
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
RAW_PATH = os.path.join(PROJECT_DIR, "09._평균속도.csv")
OUT_PATH = os.path.join(SCRIPT_DIR, "09._평균속도_preprocessed.csv")

df = pd.read_csv(RAW_PATH, encoding="utf-8-sig", low_memory=False)
print(f"원본 row: {len(df)}")

df = df[["v_link_id", "timeslot", "velocity_AVRG", "probe"]].copy()

# 숫자 변환 (문자열 섞인 행 처리)
for c in ["v_link_id", "timeslot", "velocity_AVRG", "probe"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

before = len(df)
df = df.dropna(subset=["v_link_id", "timeslot", "velocity_AVRG"]).reset_index(drop=True)
dropped = before - len(df)
if dropped > 0:
    print(f"비정상 행 제거: {dropped}개")

# 음수 클리핑
df["velocity_AVRG"] = df["velocity_AVRG"].clip(lower=0)
df["probe"] = df["probe"].fillna(0).clip(lower=0)

# v_link_id, timeslot 정수 변환
df["v_link_id"] = df["v_link_id"].astype(int)
df["timeslot"] = df["timeslot"].astype(int)
df["probe"] = df["probe"].astype(int)

# IQR 이상치 플래그 (velocity_AVRG 기준)
nonzero = df.loc[df["velocity_AVRG"] > 0, "velocity_AVRG"]
q1, q3 = nonzero.quantile(0.25), nonzero.quantile(0.75)
upper = q3 + 1.5 * (q3 - q1)

df["outlier_flag"] = df["velocity_AVRG"] > upper

print(f"\n--- 전처리 결과 ---")
print(f"최종 row: {len(df)}")
print(f"v_link_id 수: {df['v_link_id'].nunique()}")
print(f"timeslot 범위: {df['timeslot'].min()} ~ {df['timeslot'].max()}")
print(f"\nvelocity_AVRG 통계:\n{df['velocity_AVRG'].describe().to_string()}")
print(f"\nIQR 상한: {upper:.2f}")
print(f"이상치 수: {df['outlier_flag'].sum()}개 ({df['outlier_flag'].mean()*100:.1f}%)")

df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
print(f"\n저장 완료: {OUT_PATH}")
