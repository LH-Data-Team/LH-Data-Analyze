# -*- coding: utf-8 -*-
"""
검증: 0~10세 + 10~15세 = 0~15세 인지 확인
"""
import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

df_10 = pd.read_csv(os.path.join(BASE_DIR, "sgis_grid_child_pop_0to10.csv"))
df_1015 = pd.read_csv(os.path.join(BASE_DIR, "sgis_grid_child_pop_10to15.csv"))
df_15 = pd.read_csv(os.path.join(BASE_DIR, "sgis_grid_child_pop.csv"))

print(f"0~10세:  {len(df_10)}개 격자")
print(f"10~15세: {len(df_1015)}개 격자")
print(f"0~15세:  {len(df_15)}개 격자")

# gid 기준 outer merge (모든 격자 포함)
merged = df_10[["gid", "pop"]].rename(columns={"pop": "pop_0to10"}).merge(
    df_1015[["gid", "pop"]].rename(columns={"pop": "pop_10to15"}),
    on="gid", how="outer",
)
merged = merged.merge(
    df_15[["gid", "pop"]].rename(columns={"pop": "pop_0to15"}),
    on="gid", how="outer",
)
merged = merged.fillna(0)

# 합산 비교
merged["sum_check"] = merged["pop_0to10"] + merged["pop_10to15"]
merged["diff"] = merged["sum_check"] - merged["pop_0to15"]

print(f"\n병합 후 총 격자: {len(merged)}개")

# 1. 격자 수 비교
gids_10 = set(df_10["gid"])
gids_1015 = set(df_1015["gid"])
gids_15 = set(df_15["gid"])
gids_union = gids_10 | gids_1015

print(f"\n[격자 ID 비교]")
print(f"  0~10세 ∪ 10~15세: {len(gids_union)}개")
print(f"  0~15세:           {len(gids_15)}개")
print(f"  0~15에만 있는 격자: {len(gids_15 - gids_union)}개")
print(f"  합집합에만 있는 격자: {len(gids_union - gids_15)}개")

# 2. 인구 합산 비교
exact_match = (merged["diff"] == 0).sum()
close_match = (merged["diff"].abs() <= 1).sum()
mismatch = (merged["diff"].abs() > 1).sum()

print(f"\n[인구 합산 비교] (0~10 + 10~15) vs (0~15)")
print(f"  정확 일치 (diff=0):  {exact_match}개")
print(f"  근사 일치 (|diff|≤1): {close_match}개")
print(f"  불일치 (|diff|>1):   {mismatch}개")

if mismatch > 0:
    print(f"\n[불일치 상위 10개]")
    bad = merged[merged["diff"].abs() > 1].sort_values("diff", key=abs, ascending=False).head(10)
    print(bad.to_string(index=False))

# 3. 총합 비교
total_sum = merged["sum_check"].sum()
total_15 = merged["pop_0to15"].sum()
print(f"\n[총 인구 합계]")
print(f"  0~10 + 10~15 합계: {total_sum:.0f}")
print(f"  0~15 합계:         {total_15:.0f}")
print(f"  차이:              {total_sum - total_15:.0f}")
