# -*- coding: utf-8 -*-
"""
선형 보간으로 0~12세 격자별 아동인구 추정

계산식:
  10~15세 인구 = (0~15세) - (0~10세)
  10~12세 추정 = (10~15세) × 2/5  (균등 분포 가정)
  0~12세 추정  = (0~10세) + 10~12세 추정

입력:
  sgis_grid_child_pop.csv       (0~15세)
  sgis_grid_child_pop_0to10.csv (0~10세)

출력:
  sgis_grid_child_pop_0to12.csv (gid, sigungu, pop_0to12)
"""
import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

df_15 = pd.read_csv(os.path.join(BASE_DIR, "sgis_grid_child_pop.csv"))
df_10 = pd.read_csv(os.path.join(BASE_DIR, "sgis_grid_child_pop_0to10.csv"))

print(f"0~15세: {len(df_15)}개 격자")
print(f"0~10세: {len(df_10)}개 격자")

df = df_15.rename(columns={"pop": "pop_0to15"}).merge(
    df_10[["gid", "pop"]].rename(columns={"pop": "pop_0to10"}),
    on="gid",
    how="left",
)

# 결측치 처리
df["pop_0to10"] = pd.to_numeric(df["pop_0to10"], errors="coerce").fillna(0)
df["pop_0to15"] = pd.to_numeric(df["pop_0to15"], errors="coerce").fillna(0)

# 선형 보간: 0~12세 = 0~10세 + (0~15세 - 0~10세) × 2/5
df["pop_0to12"] = df["pop_0to10"] + (df["pop_0to15"] - df["pop_0to10"]) * 2 / 5
df["pop_0to12"] = df["pop_0to12"].clip(lower=0).round().astype(int)

df = df[["gid", "sigungu", "pop_0to12"]]

output = os.path.join(BASE_DIR, "sgis_grid_child_pop_0to12.csv")
df.to_csv(output, index=False, encoding="utf-8-sig")

print(f"\n결과: {len(df)}개 격자 → {output}")
print(f"\n샘플 5개:")
print(df.head().to_string(index=False))
print(f"\n통계:")
print(df["pop_0to12"].describe().round(1).to_string())
