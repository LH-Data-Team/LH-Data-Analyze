# -*- coding: utf-8 -*-
"""09._평균속도 v_link_id별 집계
- 전처리된 09번 데이터를 v_link_id 단위로 집계
- 속도 통계 + 각 통계값에 해당하는 시간대 포함
"""

import pandas as pd
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.path.join(SCRIPT_DIR, "09._평균속도_preprocessed.csv")
OUT_PATH = os.path.join(SCRIPT_DIR, "09._평균속도_agg.csv")

df = pd.read_csv(SRC_PATH, encoding="utf-8-sig")
print(f"입력 row: {len(df)}")

# v_link_id별 timeslot 평균속도 계산 (동일 v_link_id+timeslot 중복 대비)
ts_avg = df.groupby(["v_link_id", "timeslot"]).agg(
    vel=("velocity_AVRG", "mean"),
    probe=("probe", "mean"),
).reset_index()

# v_link_id별 집계
def agg_link(g):
    vel_mean = g["vel"].mean()
    vel_min = g["vel"].min()
    vel_max = g["vel"].max()
    vel_std = g["vel"].std()
    probe_mean = g["probe"].mean()

    # 평균에 가장 가까운 시간대
    ts_vel_mean = g.loc[(g["vel"] - vel_mean).abs().idxmin(), "timeslot"]
    ts_vel_min = g.loc[g["vel"].idxmin(), "timeslot"]
    ts_vel_max = g.loc[g["vel"].idxmax(), "timeslot"]
    ts_probe_mean_closest = g.loc[(g["probe"] - probe_mean).abs().idxmin(), "timeslot"]

    return pd.Series({
        "vel_mean": round(vel_mean, 2),
        "vel_min": round(vel_min, 2),
        "vel_max": round(vel_max, 2),
        "vel_std": round(vel_std, 2) if pd.notna(vel_std) else 0,
        "probe_mean": round(probe_mean, 2),
        "ts_vel_mean": int(ts_vel_mean),
        "ts_vel_min": int(ts_vel_min),
        "ts_vel_max": int(ts_vel_max),
        "ts_probe_mean": int(ts_probe_mean_closest),
    })

result = ts_avg.groupby("v_link_id").apply(agg_link, include_groups=False).reset_index()

# IQR 이상치 플래그 (vel_mean 기준)
nonzero = result.loc[result["vel_mean"] > 0, "vel_mean"]
q1, q3 = nonzero.quantile(0.25), nonzero.quantile(0.75)
upper = q3 + 1.5 * (q3 - q1)
result["outlier_flag"] = result["vel_mean"] > upper

# 정수 컬럼 변환
for c in ["ts_vel_mean", "ts_vel_min", "ts_vel_max", "ts_probe_mean"]:
    result[c] = result[c].astype(int)

print(f"\n--- 집계 결과 ---")
print(f"v_link_id 수: {len(result)}")
print(f"\nvel_mean 통계:\n{result['vel_mean'].describe().to_string()}")
print(f"\nIQR 상한: {upper:.2f}")
print(f"이상치 수: {result['outlier_flag'].sum()}개 ({result['outlier_flag'].mean()*100:.1f}%)")
print(f"\n최저속도 다발 시간대 (ts_vel_min):\n{result['ts_vel_min'].value_counts().head(5).to_string()}")
print(f"\n최고속도 다발 시간대 (ts_vel_max):\n{result['ts_vel_max'].value_counts().head(5).to_string()}")

result.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
print(f"\n저장 완료: {OUT_PATH}")
