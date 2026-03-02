"""
STEP 09 - 엔트로피 가중법으로 보정 계수 가중치 산출
- 입력: epdo_analysis/output/08_격자_종합위험지수.csv
- 출력: epdo_analysis/output/09_엔트로피_가중치.csv

엔트로피 가중법 (Entropy Weight Method):
  변동이 클수록 정보량이 많다 → 가중치 높음
  변동이 작을수록 정보량이 없다 → 가중치 낮음

4단계:
  1. 정규화: 각 인자를 0~1 범위로 통일
  2. 비율 계산: 각 격자의 인자가 전체에서 차지하는 비중
  3. 엔트로피 계산: 값이 균일할수록 엔트로피 → 1 (정보 없음)
  4. 가중치 산출: (1 - 엔트로피) 정규화
"""

import csv
import math
import os

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INPUT_PATH  = os.path.join(BASE_DIR, "epdo_analysis", "output", "08_격자_종합위험지수.csv")
OUTPUT_PATH = os.path.join(BASE_DIR, "epdo_analysis", "output", "09_엔트로피_가중치.csv")

# ── 가중치를 산출할 인자 목록 ─────────────────────────────────────────────────
# composite_risk 공식의 7개 보정 인자
FACTORS = {
    "elderly_res_ratio":  "노인거주비율     (03 거주인구)",
    "vuln_float_ratio":   "교통약자유동비율  (04 유동인구)",
    "gap_cnt":            "인프라공백수     (STEP 06)",
    "grid_avg_speed":     "격자평균속도     (09 속도)",
    "grid_congestion":    "혼잡위험도       (11·12 혼잡강도)",
    "vuln_peak_pop":      "취약시간대인구   (05·06 시간대인구)",
    "weekend_ratio":      "주말방문비율     (07 서비스인구)",
}

FACTOR_KEYS = list(FACTORS.keys())


# ── 통계 유틸 ─────────────────────────────────────────────────────────────────

def normalize_minmax(values):
    """최솟값-최댓값 정규화 → 0~1"""
    v_min = min(values)
    v_max = max(values)
    denom = v_max - v_min
    if denom == 0:
        return [0.5] * len(values)   # 모두 같으면 0.5로 처리
    return [(v - v_min) / denom for v in values]


def entropy_weight(matrix):
    """
    matrix: dict { factor_key: [값1, 값2, ..., 값n] }
    반환  : dict { factor_key: weight }
    """
    n = len(next(iter(matrix.values())))   # 격자 수
    k = 1.0 / math.log(n)                 # 정규화 상수

    entropies = {}
    for key, values in matrix.items():
        norm = normalize_minmax(values)

        # 비율 계산 (0 방지를 위해 tiny 값 추가)
        total = sum(norm) or 1.0
        p = [v / total for v in norm]

        # 엔트로피: ej = -k × Σ(pij × ln(pij))
        e = 0.0
        for pi in p:
            if pi > 0:
                e += pi * math.log(pi)
        entropies[key] = -k * e

    # 편차 dj = 1 - ej
    deviations = {k: 1.0 - e for k, e in entropies.items()}

    # 가중치 wj = dj / Σdj
    total_dev = sum(deviations.values())
    weights = {k: round(d / total_dev, 6) for k, d in deviations.items()}

    return entropies, deviations, weights


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("STEP 09 - 엔트로피 가중법 가중치 산출")
    print("=" * 60)

    # 1. 데이터 로드
    print("\n[1] 데이터 로드 중...")
    rows = []
    with open(INPUT_PATH, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    print(f"    격자 수: {len(rows):,}개")

    # 2. 인자별 값 추출 (빈 값은 0 또는 평균 대체)
    print("\n[2] 인자별 데이터 추출 중...")
    matrix = {}
    missing_info = {}

    for key in FACTOR_KEYS:
        raw = []
        missing = 0
        for row in rows:
            val = row.get(key, "")
            if val == "" or val is None:
                missing += 1
                raw.append(None)
            else:
                try:
                    raw.append(float(val))
                except ValueError:
                    missing += 1
                    raw.append(None)

        # 결측값 처리: 비결측 평균으로 대체
        valid = [v for v in raw if v is not None]
        avg = sum(valid) / len(valid) if valid else 0.0
        filled = [v if v is not None else avg for v in raw]

        matrix[key] = filled
        missing_info[key] = missing

    for key, miss in missing_info.items():
        pct = miss / len(rows) * 100
        fill_note = f"(결측 {miss}개 → 평균 {sum(v for v in matrix[key])/len(matrix[key]):.4f}으로 대체)" if miss > 0 else ""
        print(f"    {key:25s}: {len(rows)-miss:4d}개 유효  {fill_note}")

    # 3. 엔트로피 가중치 계산
    print("\n[3] 엔트로피 가중치 계산 중...")
    entropies, deviations, weights = entropy_weight(matrix)

    # 가중치 기준 내림차순 정렬
    sorted_keys = sorted(weights, key=lambda k: -weights[k])

    # 4. 결과 출력
    print("\n" + "=" * 60)
    print("  [결과] 인자별 엔트로피 가중치")
    print("=" * 60)
    print(f"\n  {'순위':>3}  {'인자':25s}  {'엔트로피':>10}  {'편차':>8}  {'가중치':>8}  설명")
    print("  " + "-" * 80)

    result = []
    for rank, key in enumerate(sorted_keys, 1):
        desc = FACTORS[key]
        e    = entropies[key]
        d    = deviations[key]
        w    = weights[key]
        bar  = "█" * int(w * 100)

        print(f"  {rank:>3}. {key:25s}  {e:10.6f}  {d:8.6f}  {w:8.4%}  {desc}")
        print(f"       {bar}")

        result.append({
            "순위":   rank,
            "인자":   key,
            "설명":   desc,
            "엔트로피": round(e, 6),
            "편차":   round(d, 6),
            "가중치": round(w, 6),
            "가중치(%)": f"{w*100:.2f}%",
        })

    print()

    # 5. 현재 공식 vs 가중치 적용 공식 비교
    print("=" * 60)
    print("  [현재 공식] — 모든 인자 동등 가중 (곱셈)")
    print("=" * 60)
    print("""
  composite_risk = EPDO
    × vuln_correction    (노인거주 + 교통약자유동)
    × infra_penalty      (인프라공백)
    × speed_weight       (속도)
    × congestion_factor  (혼잡강도)
    × peak_factor        (취약시간 인구)
    × weekend_factor     (주말비율)
""")

    print("=" * 60)
    print("  [가중치 적용 공식] — 엔트로피 가중합")
    print("=" * 60)

    # 가중합 방식으로 변환
    factor_map = {
        "elderly_res_ratio": "elderly_res_ratio",
        "vuln_float_ratio":  "vuln_float_ratio",
        "gap_cnt":           "gap_cnt / 9",
        "grid_avg_speed":    "grid_avg_speed / 60",
        "grid_congestion":   "grid_congestion / 100",
        "vuln_peak_pop":     "peak_factor - 1",
        "weekend_ratio":     "weekend_ratio",
    }

    print("\n  보정지수 = Σ(가중치 × 정규화된 인자값)")
    print()
    for key in sorted_keys:
        w = weights[key]
        expr = factor_map.get(key, key)
        print(f"    {w:.4%} × {expr:35s}  ({FACTORS[key]})")

    print("""
  composite_risk = EPDO × (1 + 보정지수)

  ※ 1을 더하는 이유: EPDO가 0인 격자도 보정값이 0보다 크게 만들기 위함
""")

    # 6. 해석 안내
    print("=" * 60)
    print("  [해석 가이드]")
    print("=" * 60)
    top3 = sorted_keys[:3]
    low3 = sorted_keys[-3:]
    print(f"\n  가중치 상위 3개 (가장 중요한 인자):")
    for k in top3:
        print(f"    → {k}: {weights[k]:.4%}  ─  {FACTORS[k]}")
    print(f"\n  가중치 하위 3개 (덜 중요한 인자):")
    for k in low3:
        print(f"    → {k}: {weights[k]:.4%}  ─  {FACTORS[k]}")

    print("""
  ※ 가중치가 높다 = 격자마다 값이 많이 달랐다 = 차별화 능력이 높다
  ※ 가중치가 낮다 = 격자마다 값이 비슷했다  = 차별화 능력이 낮다
  ※ 이는 "더 중요한 인자"가 아닌 "더 많이 변동하는 인자"임을 주의
     전문가 판단(AHP)과 병행하면 더 신뢰성 높은 가중치 산출 가능
""")

    # 7. CSV 저장
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    cols = list(result[0].keys())
    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(result)

    print(f"저장: {OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
