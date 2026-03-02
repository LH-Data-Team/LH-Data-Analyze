"""
STEP 07 - ML 기반 교통사고 위험도 예측 (Random Forest)
- 입력: output/격자별_통합데이터.csv          (17,577개 전체 격자 인프라)
        epdo_analysis/output/05_격자별_EPDO_인프라통합.csv (5,723개 사고 격자 EPDO)
- 출력: epdo_analysis/output/07_ML_피처중요도.csv
        epdo_analysis/output/07_ML_위험도예측.csv

모델 설명:
  - 전체 17,577개 격자를 대상으로 학습 (사고 없는 격자 → 저위험)
  - 고위험 기준: epdo_total ≥ 69점 (전체 사고 격자 상위 25%)
  - 인프라 변수 12개를 Feature로 사용
  - class_weight='balanced': 저위험(11,854개) vs 고위험(1,480개) 불균형 보정
  - 활용: 하남교산 등 신도시의 인프라 계획 데이터만으로 사전 위험도 예측 가능
"""

import csv
import os

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (classification_report, confusion_matrix,
                              f1_score, roc_auc_score)
from sklearn.model_selection import train_test_split

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GRID_FILE   = os.path.join(BASE_DIR, "output", "격자별_통합데이터.csv")
EPDO_FILE   = os.path.join(BASE_DIR, "epdo_analysis", "output", "05_격자별_EPDO_인프라통합.csv")
OUT_FEAT    = os.path.join(BASE_DIR, "epdo_analysis", "output", "07_ML_피처중요도.csv")
OUT_PRED    = os.path.join(BASE_DIR, "epdo_analysis", "output", "07_ML_위험도예측.csv")

HIGH_RISK_THRESHOLD = 69.0   # epdo_total 기준 고위험 (상위 25%)

FEATURES = [
    "crosswalk_cnt", "child_zone_cnt", "school_cnt",
    "kindergarten_cnt", "kindergarten_child_cnt", "daycare_cnt",
    "bus_stop_cnt", "cctv_cnt", "cctv_cam_cnt",
    "speedbump_cnt", "speedbump_hght_below", "speedbump_hght_above",
]


def main():
    print("=" * 60)
    print("STEP 07 - ML 기반 교통사고 위험도 예측 (Random Forest)")
    print("=" * 60)

    # ── 1. 데이터 로드 ──────────────────────────────────────────
    print("\n[1] 데이터 로드 중...")
    grid_df = pd.read_csv(GRID_FILE, encoding="utf-8-sig")
    epdo_df = pd.read_csv(EPDO_FILE, encoding="utf-8-sig")

    print(f"    전체 격자: {len(grid_df):,}개")
    print(f"    사고 격자: {len(epdo_df):,}개")

    # ── 2. 데이터 병합 ──────────────────────────────────────────
    print("\n[2] 데이터 병합 중...")

    # EPDO에서 필요한 컬럼만 추출
    epdo_slim = epdo_df[["grid_gid", "epdo_total"]].copy()

    # LEFT JOIN: 전체 격자 + EPDO (없으면 0)
    df = grid_df.merge(epdo_slim, on="grid_gid", how="left")
    df["epdo_total"] = df["epdo_total"].fillna(0.0)

    # 고위험 라벨 생성
    df["is_high_risk"] = (df["epdo_total"] >= HIGH_RISK_THRESHOLD).astype(int)

    high = df["is_high_risk"].sum()
    low  = len(df) - high
    print(f"    고위험(1): {high:,}개 ({high/len(df)*100:.1f}%)")
    print(f"    저위험(0): {low:,}개 ({low/len(df)*100:.1f}%)")

    # ── 3. Feature / Target 구성 ────────────────────────────────
    print("\n[3] 피처 구성 중...")
    for col in FEATURES:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    X = df[FEATURES].values
    y = df["is_high_risk"].values

    # ── 4. Train / Test Split ────────────────────────────────────
    X_train, X_test, y_train, y_test, idx_train, idx_test = train_test_split(
        X, y, df.index, test_size=0.2, random_state=42, stratify=y
    )
    print(f"    훈련셋: {len(X_train):,}개 | 테스트셋: {len(X_test):,}개")

    # ── 5. 모델 학습 ────────────────────────────────────────────
    print("\n[4] Random Forest 학습 중...")
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        class_weight="balanced",   # 불균형 보정
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    print("    학습 완료")

    # ── 6. 평가 ─────────────────────────────────────────────────
    print("\n[5] 모델 평가...")
    y_pred      = model.predict(X_test)
    y_prob      = model.predict_proba(X_test)[:, 1]
    auc         = roc_auc_score(y_test, y_prob)

    print(f"\n  ROC-AUC:  {auc:.4f}")
    print(f"\n  분류 리포트:")
    print(classification_report(y_test, y_pred,
                                 target_names=["저위험", "고위험"],
                                 digits=3))

    cm = confusion_matrix(y_test, y_pred)
    print(f"  Confusion Matrix:")
    print(f"            예측저위험  예측고위험")
    print(f"  실제저위험  {cm[0,0]:>7}   {cm[0,1]:>7}")
    print(f"  실제고위험  {cm[1,0]:>7}   {cm[1,1]:>7}")

    # ── 7. 피처 중요도 저장 ─────────────────────────────────────
    print("\n[6] 피처 중요도 저장 중...")
    importances = model.feature_importances_
    feat_rows = sorted(
        [{"feature": f, "importance": round(float(imp), 6)}
         for f, imp in zip(FEATURES, importances)],
        key=lambda x: -x["importance"]
    )

    os.makedirs(os.path.dirname(OUT_FEAT), exist_ok=True)
    with open(OUT_FEAT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["rank", "feature", "importance"])
        w.writeheader()
        for i, row in enumerate(feat_rows, 1):
            w.writerow({"rank": i, **row})

    print(f"\n  {'순위':>4} {'피처':25s} {'중요도':>10}")
    print("  " + "-" * 44)
    for i, r in enumerate(feat_rows, 1):
        bar = "#" * int(r["importance"] * 200)
        print(f"  {i:>4} {r['feature']:25s} {r['importance']:>10.4f}  {bar}")

    # ── 8. 전체 격자 예측 결과 저장 ─────────────────────────────
    print("\n[7] 전체 격자 예측 중...")
    all_prob  = model.predict_proba(X)[:, 1]
    all_pred  = model.predict(X)

    df["risk_prob"]     = np.round(all_prob, 4)
    df["predicted_risk"]= all_pred

    out_cols = ["grid_gid", "epdo_total", "is_high_risk", "risk_prob", "predicted_risk"]
    df[out_cols].to_csv(OUT_PRED, index=False, encoding="utf-8-sig")

    # 요약
    pred_high = int(all_pred.sum())
    print(f"    예측 고위험 격자: {pred_high:,}개 (실제: {high:,}개)")

    print(f"\n  risk_prob 상위 10개 격자 (예측 위험도 높은 순):")
    top10 = df.nlargest(10, "risk_prob")[
        ["grid_gid", "epdo_total", "is_high_risk", "risk_prob"]
    ]
    print(f"  {'격자ID':12s} {'실제EPDO':>9} {'실제라벨':>6} {'위험확률':>8}")
    print("  " + "-" * 42)
    for _, r in top10.iterrows():
        label = "고위험" if r["is_high_risk"] else "저위험"
        print(f"  {r['grid_gid']:12s} {r['epdo_total']:>9.1f}  {label:>6}  {r['risk_prob']:>8.4f}")

    print(f"\n저장: {OUT_FEAT}")
    print(f"저장: {OUT_PRED}")
    print("=" * 60)


if __name__ == "__main__":
    main()
