# -*- coding: utf-8 -*-
"""12._혼잡시간강도 전처리
- 08번과 중복되는 컬럼 제거
- v_link_id, TI_CG만 유지
- 음수 클리핑, IQR 이상치 플래그
"""

import pandas as pd
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
RAW_PATH = os.path.join(PROJECT_DIR, "12._혼잡시간강도.csv")
OUT_PATH = os.path.join(SCRIPT_DIR, "12._혼잡시간강도_preprocessed.csv")

df = pd.read_csv(RAW_PATH, encoding="utf-8-sig", low_memory=False)
print(f"원본 row: {len(df)}")

df = df[["v_link_id", "TI_CG"]].copy()

for c in ["v_link_id", "TI_CG"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

before = len(df)
df = df.dropna().reset_index(drop=True)
dropped = before - len(df)
if dropped > 0:
    print(f"결측 행 제거: {dropped}개")

df["TI_CG"] = df["TI_CG"].clip(lower=0)
df["v_link_id"] = df["v_link_id"].astype(int)

# IQR 이상치 플래그 (0 제외 nonzero 기준)
nonzero = df.loc[df["TI_CG"] > 0, "TI_CG"]
q1, q3 = nonzero.quantile(0.25), nonzero.quantile(0.75)
upper = q3 + 1.5 * (q3 - q1)
df["outlier_flag"] = df["TI_CG"] > upper

print(f"\n--- 전처리 결과 ---")
print(f"최종 row: {len(df)}")
print(f"TI_CG == 0: {(df['TI_CG'] == 0).sum()}개")
print(f"\nTI_CG 통계:\n{df['TI_CG'].describe().to_string()}")
print(f"\nIQR 상한: {upper:.2f}")
print(f"이상치 수: {df['outlier_flag'].sum()}개 ({df['outlier_flag'].mean()*100:.1f}%)")

df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
print(f"\n저장 완료: {OUT_PATH}")
