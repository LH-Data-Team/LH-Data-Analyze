# -*- coding: utf-8 -*-
"""05._시간대별_직장인구 전처리"""

import pandas as pd
import numpy as np
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_PATH = os.path.join(BASE_DIR, "05._시간대별_직장인구.csv")
OUT_PATH = os.path.join(BASE_DIR, "05._시간대별_직장인구_preprocessed.csv")

# ── 1. 데이터 로드 ──────────────────────────────────────────
df = pd.read_csv(RAW_PATH, encoding="utf-8-sig")
print(f"[원본] 행: {len(df):,}  |  컬럼: {list(df.columns)}")

# ── 2. 사용할 컬럼만 추출 ───────────────────────────────────
tmst_cols = [f"TMST_{h:02d}" for h in range(24)]
use_cols = ["gbn"] + tmst_cols + ["lon", "lat"]
df = df[use_cols].copy()
print(f"\n[컬럼 선택] {use_cols}")

# ── 3. 결측치 현황 확인 ─────────────────────────────────────
total_cells = len(df) * len(tmst_cols)
missing_cells = df[tmst_cols].isna().sum().sum()
all_missing_rows = df[tmst_cols].isna().all(axis=1).sum()

print(f"\n[결측치 현황]")
print(f"  전체 셀: {total_cells:,}")
print(f"  결측 셀: {missing_cells:,} ({missing_cells / total_cells * 100:.1f}%)")
print(f"  모든 시간대가 결측인 행: {all_missing_rows:,} / {len(df):,}")
print(f"\n  컬럼별 결측률:")
for c in tmst_cols:
    n = df[c].isna().sum()
    print(f"    {c:10s}: {n:>7,} ({n / len(df) * 100:.1f}%)")

coord_missing = df[["lon", "lat"]].isna().any(axis=1).sum()
print(f"\n  좌표(lon/lat) 결측 행: {coord_missing:,}")

# ── 4. 결측치 처리 ──────────────────────────────────────────
# 특정 시간대 결측 = 해당 시간에 직장인구 없음
df[tmst_cols] = df[tmst_cols].fillna(0)

if coord_missing > 0:
    before = len(df)
    df = df.dropna(subset=["lon", "lat"]).reset_index(drop=True)
    print(f"\n[좌표 결측 행 제거] {before - len(df):,}행 제거")

# ── 5. 빈 격자 제거 (모든 시간대가 0인 행) ───────────────────
before = len(df)
df = df[df[tmst_cols].sum(axis=1) > 0].reset_index(drop=True)
removed = before - len(df)
print(f"\n[빈 격자 제거] {removed:,}행 제거 -> {len(df):,}행 남음")

# ── 6. 음수 값 확인 및 처리 ──────────────────────────────────
neg_count = (df[tmst_cols] < 0).sum().sum()
if neg_count > 0:
    print(f"\n[음수 값] {neg_count}개 발견 -> 0으로 클리핑")
    df[tmst_cols] = df[tmst_cols].clip(lower=0)
else:
    print(f"\n[음수 값] 없음 (OK)")

# ── 7. 이상치 탐지 (IQR 기반, 0 제외) ────────────────────────
print(f"\n[이상치 탐지] IQR 기반 (0 제외 분포)")
outlier_info = []
for c in tmst_cols:
    nonzero = df.loc[df[c] > 0, c]
    if len(nonzero) == 0:
        continue
    q1 = nonzero.quantile(0.25)
    q3 = nonzero.quantile(0.75)
    iqr = q3 - q1
    upper = q3 + 1.5 * iqr
    n_outlier = (nonzero > upper).sum()
    if n_outlier > 0:
        outlier_info.append({"col": c, "upper": upper})
    print(f"  {c:10s}: 비영 {len(nonzero):>6,}건 | "
          f"Q1={q1:>10.6f}  Q3={q3:>10.6f}  상한={upper:>12.6f} | "
          f"이상치={n_outlier:>5}건  max={nonzero.max():.6f}")

if outlier_info:
    df["outlier_flag"] = False
    for info in outlier_info:
        df.loc[df[info["col"]] > info["upper"], "outlier_flag"] = True
    n_flagged = df["outlier_flag"].sum()
    print(f"\n  -> 이상치 플래그 행: {n_flagged:,}건 (제거하지 않음, 참고용)")

# ── 8. 전처리 후 기본 통계 ───────────────────────────────────
print(f"\n[전처리 후 기본 통계]")
print(df[tmst_cols].describe().round(6).to_string())

# ── 9. 저장 ──────────────────────────────────────────────────
df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
print(f"\n[저장 완료] {OUT_PATH}")
print(f"  최종 행: {len(df):,}  |  컬럼: {list(df.columns)}")
