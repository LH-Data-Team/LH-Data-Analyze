# -*- coding: utf-8 -*-
"""05._시간대별_직장인구 전처리"""

import pandas as pd
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
RAW_PATH = os.path.join(PROJECT_DIR, "05._시간대별_직장인구.csv")
OUT_PATH = os.path.join(SCRIPT_DIR, "05._시간대별_직장인구_preprocessed.csv")

df = pd.read_csv(RAW_PATH, encoding="utf-8-sig")

tmst_cols = [f"TMST_{h:02d}" for h in range(24)]
df = df[["gbn"] + tmst_cols + ["lon", "lat"]].copy()

df[tmst_cols] = df[tmst_cols].fillna(0)
df = df.dropna(subset=["lon", "lat"]).reset_index(drop=True)
df[tmst_cols] = df[tmst_cols].clip(lower=0)

outlier_info = []
for c in tmst_cols:
    nonzero = df.loc[df[c] > 0, c]
    if len(nonzero) == 0:
        continue
    q1, q3 = nonzero.quantile(0.25), nonzero.quantile(0.75)
    upper = q3 + 1.5 * (q3 - q1)
    if (nonzero > upper).sum() > 0:
        outlier_info.append({"col": c, "upper": upper})

if outlier_info:
    df["outlier_flag"] = False
    for info in outlier_info:
        df.loc[df[info["col"]] > info["upper"], "outlier_flag"] = True

df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
