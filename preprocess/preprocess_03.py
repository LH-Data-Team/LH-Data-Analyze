# -*- coding: utf-8 -*-
"""03._성연령별_거주인구(격자) 전처리"""

import pandas as pd
import numpy as np
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_PATH = os.path.join(BASE_DIR, "03._성연령별_거주인구(격자).csv")
OUT_PATH = os.path.join(BASE_DIR, "03._성연령별_거주인구(격자)_preprocessed.csv")

# ── 1. 데이터 로드 ──────────────────────────────────────────
df = pd.read_csv(RAW_PATH, encoding="utf-8-sig")
print(f"[원본] 행: {len(df):,}  |  컬럼: {list(df.columns)}")

# 현재: 모든 m_, w_ 컬럼을 자동 선택
pop_cols = [c for c in df.columns if c.startswith(("m_", "w_"))]
use_cols = ["gid"] + pop_cols
df = df[use_cols].copy()
print(f"\n[컬럼 선택] {use_cols}")

# ── 3. 결측치 현황 확인 ─────────────────────────────────────
total_cells = len(df) * len(pop_cols)
missing_cells = df[pop_cols].isna().sum().sum()
all_missing_rows = df[pop_cols].isna().all(axis=1).sum()

print(f"\n[결측치 현황]")
print(f"  전체 셀: {total_cells:,}")
print(f"  결측 셀: {missing_cells:,} ({missing_cells / total_cells * 100:.1f}%)")
print(f"  모든 인구 컬럼이 결측인 행: {all_missing_rows:,} / {len(df):,} ({all_missing_rows / len(df) * 100:.1f}%)")
print(f"\n  컬럼별 결측률:")
for c in pop_cols:
    n = df[c].isna().sum()
    print(f"    {c:15s}: {n:>7,} ({n / len(df) * 100:.1f}%)")

# ── 4. 결측치 처리: 0으로 채우기 ─────────────────────────────
# 격자별 거주인구에서 결측 = 해당 연령대 인구 없음 또는 비밀보호 비공개
df[pop_cols] = df[pop_cols].fillna(0)

# ── 5. 빈 격자 제거 (모든 인구 컬럼이 0인 행) ────────────────
before = len(df)
df = df[df[pop_cols].sum(axis=1) > 0].reset_index(drop=True)
removed = before - len(df)
print(f"\n[빈 격자 제거] {removed:,}행 제거 → {len(df):,}행 남음")

# ── 6. 음수 값 확인 및 처리 ──────────────────────────────────
neg_count = (df[pop_cols] < 0).sum().sum()
if neg_count > 0:
    print(f"\n[음수 값] {neg_count}개 발견 → 0으로 클리핑")
    df[pop_cols] = df[pop_cols].clip(lower=0)
else:
    print(f"\n[음수 값] 없음 (OK)")

# ── 7. 이상치 탐지 (IQR 기반, 0 제외 후 계산) ────────────────
# 인구 데이터는 0이 매우 많으므로, 0을 제외한 분포에서 이상치 판단
print(f"\n[이상치 탐지] IQR 기반 (0 제외 분포)")
outlier_info = []
for c in pop_cols:
    nonzero = df.loc[df[c] > 0, c]
    if len(nonzero) == 0:
        continue
    q1 = nonzero.quantile(0.25)
    q3 = nonzero.quantile(0.75)
    iqr = q3 - q1
    upper = q3 + 1.5 * iqr
    n_outlier = (nonzero > upper).sum()
    if n_outlier > 0:
        outlier_info.append({
            "컬럼": c,
            "Q1": q1,
            "Q3": q3,
            "상한": upper,
            "이상치수": n_outlier,
            "최대값": nonzero.max(),
        })
    print(f"  {c:15s}: 비영 {len(nonzero):>5,}건 | "
          f"Q1={q1:>6.1f}  Q3={q3:>6.1f}  상한={upper:>7.1f} | "
          f"이상치={n_outlier:>4}건  max={nonzero.max():.1f}")

# 이상치는 실제 밀집 지역일 수 있으므로 제거하지 않고 플래그만 생성
if outlier_info:
    df["outlier_flag"] = False
    for info in outlier_info:
        c = info["컬럼"]
        upper = info["상한"]
        df.loc[df[c] > upper, "outlier_flag"] = True
    n_flagged = df["outlier_flag"].sum()
    print(f"\n  → 이상치 플래그 행: {n_flagged:,}건 (제거하지 않음, 참고용)")

# ── 8. 전처리 후 기본 통계 ───────────────────────────────────
print(f"\n[전처리 후 기본 통계]")
print(df[pop_cols].describe().round(2).to_string())

# ── 9. 저장 ──────────────────────────────────────────────────
df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
print(f"\n[저장 완료] {OUT_PATH}")
print(f"  최종 행: {len(df):,}  |  컬럼: {list(df.columns)}")
