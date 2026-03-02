"""
STEP 10 - 음이항 회귀 주축 + 엔트로피/상관계수 3중 교차검증 통합 가중치

목적:
  엔트로피 단독의 한계(변별력 ≠ 중요도)를 보완하기 위해
  음이항 회귀(NB), EPDO 상관계수(Corr), 엔트로피(Entropy) 3가지 방법으로
  각 인자의 가중치를 산출하고, 기하평균으로 통합한다.

각 방법의 역할:
  - NB 회귀    : "이 인자가 사고 건수에 실제로 얼마나 영향을 주나?" (주축)
  - Corr 가중  : "이 인자가 사고 심각도(EPDO)와 얼마나 연동되나?" (교차검증 1)
  - 엔트로피   : "이 인자가 격자를 얼마나 잘 구분하나?"           (교차검증 2)

통합 방식:
  w_final = geometric_mean(w_nb, w_corr, w_entropy) → 정규화

입력: epdo_analysis/output/08_격자_종합위험지수.csv
      epdo_analysis/output/09_엔트로피_가중치.csv
출력: epdo_analysis/output/10_통합가중치_최종.csv
"""

import csv
import math
import os

import numpy as np
import pandas as pd

# statsmodels 음이항 회귀 (없으면 Poisson fallback)
try:
    import statsmodels.api as sm
    HAS_STATSMODELS = True
except ImportError:
    from sklearn.linear_model import PoissonRegressor
    from sklearn.preprocessing import StandardScaler
    HAS_STATSMODELS = False

BASE_DIR      = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INPUT_08      = os.path.join(BASE_DIR, "epdo_analysis", "output", "08_격자_종합위험지수.csv")
INPUT_09      = os.path.join(BASE_DIR, "epdo_analysis", "output", "09_엔트로피_가중치.csv")
OUTPUT_PATH   = os.path.join(BASE_DIR, "epdo_analysis", "output", "10_통합가중치_최종.csv")

FACTORS = {
    "elderly_res_ratio": "노인거주비율",
    "vuln_float_ratio":  "교통약자유동비율",
    "gap_cnt":           "인프라공백수",
    "grid_avg_speed":    "격자평균속도",
    "grid_congestion":   "혼잡위험도",
    "vuln_peak_pop":     "취약시간대인구",
    "weekend_ratio":     "주말방문비율",
}
FACTOR_KEYS = list(FACTORS.keys())

# grid_avg_speed 는 사고와 반대 방향 → 절댓값 처리 명시
NEGATIVE_EXPECTED = {"grid_avg_speed"}


# ── 유틸 ──────────────────────────────────────────────────────────────────────

def normalize(d: dict) -> dict:
    """dict 값을 합계=1로 정규화"""
    total = sum(d.values())
    return {k: v / total for k, v in d.items()}


def geometric_mean_weights(*weight_dicts):
    """
    여러 가중치 dict의 기하평균 → 정규화
    기하평균: 각 인자마다 모든 방법 가중치를 곱해 n제곱근 취함
    """
    n = len(weight_dicts)
    keys = list(weight_dicts[0].keys())
    raw = {}
    for k in keys:
        product = 1.0
        for wd in weight_dicts:
            product *= wd[k]
        raw[k] = product ** (1.0 / n)
    return normalize(raw)


def spearman_corr(rank_a, rank_b):
    """두 순위 리스트의 스피어만 상관계수"""
    n = len(rank_a)
    d2 = sum((a - b) ** 2 for a, b in zip(rank_a, rank_b))
    return 1 - (6 * d2) / (n * (n ** 2 - 1))


# ── 1단계: 데이터 로드 ─────────────────────────────────────────────────────────

def load_data():
    df = pd.read_csv(INPUT_08, encoding="utf-8-sig")
    print(f"    총 격자 수: {len(df):,}개")

    # 결측값 처리: 비결측 평균으로 대체
    cols_needed = FACTOR_KEYS + ["accident_cnt", "epdo_total"]
    for col in cols_needed:
        if col in df.columns:
            missing = df[col].isna().sum()
            if missing > 0:
                df[col] = df[col].fillna(df[col].mean())
                print(f"    {col}: 결측 {missing}개 → 평균 대체")
        else:
            print(f"    [경고] {col} 컬럼 없음 → 0으로 채움")
            df[col] = 0.0

    # accident_cnt는 정수형
    df["accident_cnt"] = df["accident_cnt"].clip(lower=0).round().astype(int)
    return df


# ── 2단계: 음이항 회귀 → NB 가중치 ───────────────────────────────────────────

def nb_regression_weights(df):
    X_raw = df[FACTOR_KEYS].values
    y     = df["accident_cnt"].values

    # 표준화 (StandardScaler): 계수가 변수 간 직접 비교 가능해짐
    mu    = X_raw.mean(axis=0)
    sigma = X_raw.std(axis=0)
    sigma[sigma == 0] = 1.0
    X_std = (X_raw - mu) / sigma

    if HAS_STATSMODELS:
        print("    [모델] statsmodels 음이항(NegativeBinomial) 회귀")
        X_sm = sm.add_constant(X_std)
        model = sm.NegativeBinomial(y, X_sm)
        result = model.fit(disp=False, maxiter=200)
        coefs = result.params[1:]          # 상수항 제외
        pvals = result.pvalues[1:]
        model_name = "음이항 회귀 (NegativeBinomial)"
    else:
        print("    [모델] sklearn PoissonRegressor (statsmodels 미설치)")
        from sklearn.linear_model import PoissonRegressor
        reg = PoissonRegressor(max_iter=500)
        reg.fit(X_std, y)
        coefs = reg.coef_
        pvals = [None] * len(coefs)
        model_name = "푸아송 회귀 (Poisson, NB 근사)"

    # 표준화 계수 절댓값 → 정규화
    abs_coefs = {k: abs(float(coefs[i])) for i, k in enumerate(FACTOR_KEYS)}
    weights   = normalize(abs_coefs)

    return weights, abs_coefs, pvals, model_name


# ── 3단계: EPDO 상관계수 → Corr 가중치 ───────────────────────────────────────

def corr_weights(df):
    corrs = {}
    for key in FACTOR_KEYS:
        c = df[key].corr(df["epdo_total"])
        corrs[key] = abs(c)

    weights = normalize(corrs)
    return weights, corrs


# ── 4단계: 엔트로피 가중치 로드 ───────────────────────────────────────────────

def load_entropy_weights():
    entropy_w = {}
    with open(INPUT_09, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = row["인자"]
            if key in FACTOR_KEYS:
                entropy_w[key] = float(row["가중치"])
    # 혹시 누락된 인자 있으면 균등값으로 채움
    for k in FACTOR_KEYS:
        if k not in entropy_w:
            entropy_w[k] = 1.0 / len(FACTOR_KEYS)
    return normalize(entropy_w)


# ── 5단계: 합의도(★) 판정 ────────────────────────────────────────────────────

def consensus_star(nb_rank, corr_rank, ent_rank, n=7):
    """상위 절반(top 4/7) 기준 합의도"""
    threshold = n // 2 + 1   # 4
    top_count = sum([
        nb_rank   <= threshold,
        corr_rank <= threshold,
        ent_rank  <= threshold,
    ])
    return "★★★" if top_count == 3 else "★★" if top_count == 2 else "★"


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    sep = "=" * 70
    print(sep)
    print("STEP 10 - 3중 교차검증 통합 가중치 산출")
    print(sep)

    # 1. 데이터 로드
    print("\n[1] 데이터 로드")
    df = load_data()

    # 2. 음이항 회귀
    print("\n[2] 음이항 회귀 가중치 계산")
    nb_w, nb_coefs, pvals, model_name = nb_regression_weights(df)
    print(f"    사용 모델: {model_name}")

    # 3. 상관계수 가중치
    print("\n[3] EPDO 상관계수 가중치 계산")
    corr_w, corrs = corr_weights(df)
    for k in FACTOR_KEYS:
        direction = "↑" if corrs[k] >= 0 else "↓"
        print(f"    {k:25s}: r={df[k].corr(df['epdo_total']):+.4f} {direction}  → |r|={corrs[k]:.4f}")

    # 4. 엔트로피 가중치
    print("\n[4] 엔트로피 가중치 로드")
    ent_w = load_entropy_weights()
    for k in FACTOR_KEYS:
        print(f"    {k:25s}: {ent_w[k]:.6f}")

    # 5. 통합 가중치 (기하평균)
    print("\n[5] 통합 가중치 계산 (기하평균)")
    final_w = geometric_mean_weights(nb_w, corr_w, ent_w)

    # 6. 순위 산출
    nb_rank   = {k: sorted(nb_w,   key=lambda x: -nb_w[x]).index(k)  + 1 for k in FACTOR_KEYS}
    corr_rank = {k: sorted(corr_w, key=lambda x: -corr_w[x]).index(k)+ 1 for k in FACTOR_KEYS}
    ent_rank  = {k: sorted(ent_w,  key=lambda x: -ent_w[x]).index(k) + 1 for k in FACTOR_KEYS}
    final_rank= {k: sorted(final_w,key=lambda x: -final_w[x]).index(k)+1 for k in FACTOR_KEYS}

    # 7. 결과 출력
    print("\n" + sep)
    print("  [결과] 3중 교차검증 통합 가중치")
    print(sep)
    header = f"  {'인자':25s}  {'NB회귀':>8}  {'EPDO상관':>8}  {'엔트로피':>8}  {'통합':>8}  합의도  설명"
    print(f"\n{header}")
    print("  " + "-" * 85)

    sorted_keys = sorted(FACTOR_KEYS, key=lambda k: -final_w[k])
    result_rows = []

    for k in sorted_keys:
        star = consensus_star(nb_rank[k], corr_rank[k], ent_rank[k])
        desc = FACTORS[k]
        pval_str = f"p={float(pvals[FACTOR_KEYS.index(k)]):.3f}" if pvals[0] is not None else ""
        print(
            f"  {k:25s}  {nb_w[k]:8.4%}  {corr_w[k]:8.4%}  {ent_w[k]:8.4%}"
            f"  {final_w[k]:8.4%}  {star:4s}  {desc}"
        )
        result_rows.append({
            "최종순위":     final_rank[k],
            "인자":         k,
            "설명":         desc,
            "NB회귀_가중치":   round(nb_w[k],  6),
            "NB회귀_순위":     nb_rank[k],
            "EPDO상관_가중치": round(corr_w[k], 6),
            "EPDO상관_순위":   corr_rank[k],
            "엔트로피_가중치": round(ent_w[k],  6),
            "엔트로피_순위":   ent_rank[k],
            "통합가중치":    round(final_w[k], 6),
            "합의도":        star,
        })

    # 8. 스피어만 순위 상관 (방법 간 일치도)
    print(f"\n{'─'*50}")
    print("  [방법 간 스피어만 순위 상관계수]")
    nb_r   = [nb_rank[k]   for k in FACTOR_KEYS]
    corr_r = [corr_rank[k] for k in FACTOR_KEYS]
    ent_r  = [ent_rank[k]  for k in FACTOR_KEYS]
    sc_nb_corr = spearman_corr(nb_r, corr_r)
    sc_nb_ent  = spearman_corr(nb_r, ent_r)
    sc_corr_ent= spearman_corr(corr_r, ent_r)
    print(f"  NB회귀 ↔ EPDO상관:  {sc_nb_corr:+.4f}")
    print(f"  NB회귀 ↔ 엔트로피:  {sc_nb_ent:+.4f}")
    print(f"  EPDO상관 ↔ 엔트로피: {sc_corr_ent:+.4f}")

    # 9. 핵심 변수 요약
    core    = [k for k in sorted_keys if consensus_star(nb_rank[k], corr_rank[k], ent_rank[k]) == "★★★"]
    major   = [k for k in sorted_keys if consensus_star(nb_rank[k], corr_rank[k], ent_rank[k]) == "★★"]
    ref     = [k for k in sorted_keys if consensus_star(nb_rank[k], corr_rank[k], ent_rank[k]) == "★"]

    print(f"\n{'─'*50}")
    print("  [합의도 기반 변수 분류]")
    print(f"\n  ★★★ 핵심변수 (3가지 방법 모두 상위 4위 이내):")
    for k in core:
        print(f"    → {k}: 통합 {final_w[k]:.2%}  ({FACTORS[k]})")
    print(f"\n  ★★  주요변수 (2가지 방법 상위 4위 이내):")
    for k in major:
        print(f"    → {k}: 통합 {final_w[k]:.2%}  ({FACTORS[k]})")
    print(f"\n  ★   참고변수 (1가지 이하):")
    for k in ref:
        print(f"    → {k}: 통합 {final_w[k]:.2%}  ({FACTORS[k]})")

    # 10. 엔트로피 단독 대비 변화
    print(f"\n{'─'*50}")
    print("  [엔트로피 단독 → 통합 가중치 순위 변화]")
    ent_sorted  = sorted(FACTOR_KEYS, key=lambda k: -ent_w[k])
    final_sorted= sorted(FACTOR_KEYS, key=lambda k: -final_w[k])
    for k in FACTOR_KEYS:
        old = ent_rank[k]
        new = final_rank[k]
        delta = old - new
        arrow = f"▲{delta}" if delta > 0 else f"▼{abs(delta)}" if delta < 0 else "─"
        print(f"  {k:25s}: 엔트로피 {old}위 → 통합 {new}위  {arrow}")

    print(f"\n  통합 가중치 합계: {sum(final_w.values()):.6f}  (1.0 검증)")
    print()

    # 11. CSV 저장
    result_rows.sort(key=lambda r: r["최종순위"])
    cols = list(result_rows[0].keys())
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(result_rows)

    print(f"저장: {OUTPUT_PATH}")
    print(sep)

    return result_rows, final_w, sc_nb_corr, sc_nb_ent, sc_corr_ent


if __name__ == "__main__":
    main()
