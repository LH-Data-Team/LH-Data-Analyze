# -*- coding: utf-8 -*-
"""
과속방지턱 fac_hght 분석
- 0 제외 평균 산출
- 0인 row, 평균 이하, 평균 이상 개수
"""
import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
df = pd.read_csv(os.path.join(BASE_DIR, "21._과속방지턱_현황.csv"))

df["fac_hght"] = pd.to_numeric(df["fac_hght"], errors="coerce")

total = len(df)
null_cnt = df["fac_hght"].isna().sum()
orig_zero_cnt = (df["fac_hght"] == 0).sum()

df["fac_hght"] = df["fac_hght"].fillna(0)
zero_cnt = (df["fac_hght"] == 0).sum()

nonzero = df[df["fac_hght"] > 0]["fac_hght"]
avg = nonzero.mean()

below_avg = ((df["fac_hght"] > 0) & (df["fac_hght"] <= avg)).sum()
above_avg = (df["fac_hght"] > avg).sum()

print(f"전체 row: {total}개")
print(f"fac_hght 결측치(NaN): {null_cnt}개")
print(f"fac_hght 원래 0인 값: {orig_zero_cnt}개")
print(f"fac_hght == 0 (결측+원래0): {zero_cnt}개")
print(f"fac_hght 0 제외 평균: {avg:.2f}")
print(f"")
print(f"fac_hght == 0:        {zero_cnt}개")
print(f"0 < fac_hght <= 평균: {below_avg}개")
print(f"fac_hght > 평균:     {above_avg}개")
print(f"합계 검증: {zero_cnt + below_avg + above_avg}개")
