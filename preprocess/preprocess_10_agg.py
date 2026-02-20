# -*- coding: utf-8 -*-
"""10._추정교통량 v_link_id별 집계
- 전처리된 10번 데이터를 v_link_id 단위로 집계
- 교통량 통계 + 각 통계값에 해당하는 시간대 포함
"""

import pandas as pd
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.path.join(SCRIPT_DIR, "10._추정교통량_preprocessed.csv")
OUT_PATH = os.path.join(SCRIPT_DIR, "10._추정교통량_agg.csv")

df = pd.read_csv(SRC_PATH, encoding="utf-8-sig")
print(f"입력 row: {len(df)}")

aadt_cols = ["ALL_AADT", "PSCR_AADT", "BUS_AADT", "FGCR_AADT"]

# v_link_id별 timeslot 평균 (동일 조합 중복 대비)
ts_avg = df.groupby(["v_link_id", "timeslot"]).agg(
    all_aadt=("ALL_AADT", "mean"),
    pscr_aadt=("PSCR_AADT", "mean"),
    bus_aadt=("BUS_AADT", "mean"),
    fgcr_aadt=("FGCR_AADT", "mean"),
).reset_index()

def agg_link(g):
    all_mean = g["all_aadt"].mean()
    all_min = g["all_aadt"].min()
    all_max = g["all_aadt"].max()
    all_std = g["all_aadt"].std()

    ts_all_mean = g.loc[(g["all_aadt"] - all_mean).abs().idxmin(), "timeslot"]
    ts_all_min = g.loc[g["all_aadt"].idxmin(), "timeslot"]
    ts_all_max = g.loc[g["all_aadt"].idxmax(), "timeslot"]

    return pd.Series({
        "all_mean": round(all_mean, 2),
        "all_min": round(all_min, 2),
        "all_max": round(all_max, 2),
        "all_std": round(all_std, 2) if pd.notna(all_std) else 0,
        "pscr_mean": round(g["pscr_aadt"].mean(), 2),
        "bus_mean": round(g["bus_aadt"].mean(), 2),
        "fgcr_mean": round(g["fgcr_aadt"].mean(), 2),
        "ts_all_mean": int(ts_all_mean),
        "ts_all_min": int(ts_all_min),
        "ts_all_max": int(ts_all_max),
    })

result = ts_avg.groupby("v_link_id").apply(agg_link, include_groups=False).reset_index()

# IQR 이상치 플래그 (all_mean 기준)
nonzero = result.loc[result["all_mean"] > 0, "all_mean"]
q1, q3 = nonzero.quantile(0.25), nonzero.quantile(0.75)
upper = q3 + 1.5 * (q3 - q1)
result["outlier_flag"] = result["all_mean"] > upper

for c in ["ts_all_mean", "ts_all_min", "ts_all_max"]:
    result[c] = result[c].astype(int)

print(f"\n--- 집계 결과 ---")
print(f"v_link_id 수: {len(result)}")
print(f"\nall_mean 통계:\n{result['all_mean'].describe().to_string()}")
print(f"\nIQR 상한: {upper:.2f}")
print(f"이상치 수: {result['outlier_flag'].sum()}개 ({result['outlier_flag'].mean()*100:.1f}%)")
print(f"\n교통량 최대 시간대 (ts_all_max):\n{result['ts_all_max'].value_counts().head(5).to_string()}")
print(f"\n교통량 최소 시간대 (ts_all_min):\n{result['ts_all_min'].value_counts().head(5).to_string()}")
print(f"\n차종별 평균 교통량:")
print(f"  승용차: {result['pscr_mean'].mean():.1f}")
print(f"  버스:   {result['bus_mean'].mean():.1f}")
print(f"  화물차: {result['fgcr_mean'].mean():.1f}")

result.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
print(f"\n저장 완료: {OUT_PATH}")
