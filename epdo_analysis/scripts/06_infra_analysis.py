"""
STEP 06 - 인프라 공백 분석
- 입력: epdo_analysis/output/05_격자별_EPDO_인프라통합.csv
- 출력: epdo_analysis/output/06_인프라_상관분석.csv
        epdo_analysis/output/06_인프라공백_고위험격자.csv

분석 1: EPDO × 시설물 수 상관관계 (Pearson + Spearman)
  - 어떤 시설물이 EPDO와 관련 있는지 확인
분석 2: 고위험 격자(상위 25%) 중 시설물 공백 격자 추출
  - 시설물이 없거나 전체 평균의 50% 미만인 항목을 '공백'으로 판단
"""

import csv
import math
import os

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INPUT_PATH   = os.path.join(BASE_DIR, "epdo_analysis", "output", "05_격자별_EPDO_인프라통합.csv")
CORR_OUTPUT  = os.path.join(BASE_DIR, "epdo_analysis", "output", "06_인프라_상관분석.csv")
GAP_OUTPUT   = os.path.join(BASE_DIR, "epdo_analysis", "output", "06_인프라공백_고위험격자.csv")

INFRA_COLS = [
    "crosswalk_cnt", "child_zone_cnt", "school_cnt",
    "kindergarten_cnt", "daycare_cnt", "bus_stop_cnt",
    "cctv_cnt", "cctv_cam_cnt", "speedbump_cnt",
]

HIGH_RISK_PERCENTILE = 75   # 상위 25%를 고위험으로 정의


# ── 통계 유틸 ────────────────────────────────────────────────────────────────

def _mean(values):
    return sum(values) / len(values) if values else 0.0


def pearson(x, y):
    n = len(x)
    if n < 2:
        return None
    mx, my = _mean(x), _mean(y)
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    dx  = math.sqrt(sum((xi - mx) ** 2 for xi in x))
    dy  = math.sqrt(sum((yi - my) ** 2 for yi in y))
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx * dy), 4)


def rank_list(values):
    """평균 순위(동점 처리 포함) 반환"""
    indexed = sorted(enumerate(values), key=lambda t: t[1])
    ranks   = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j < len(indexed) - 1 and indexed[j + 1][1] == indexed[j][1]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = avg_rank
        i = j + 1
    return ranks


def spearman(x, y):
    return pearson(rank_list(x), rank_list(y))


def percentile(values, p):
    sv  = sorted(values)
    idx = (p / 100) * (len(sv) - 1)
    lo  = int(idx)
    hi  = min(lo + 1, len(sv) - 1)
    return sv[lo] + (idx - lo) * (sv[hi] - sv[lo])


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("STEP 06 - 인프라 공백 분석")
    print("=" * 60)

    # 1. 데이터 로드
    rows = []
    with open(INPUT_PATH, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    print(f"\n[1] 격자 수: {len(rows):,}개 로드 완료")

    epdo_vals = [float(r["epdo_total"]) for r in rows]

    # ── 분석 1: 상관관계 ─────────────────────────────────────────────────────
    print("\n[2] EPDO × 시설물 상관관계 분석 중...")
    corr_result = []
    for col in INFRA_COLS:
        infra_vals    = [float(r.get(col, 0) or 0) for r in rows]
        pr            = pearson(epdo_vals, infra_vals)
        sr            = spearman(epdo_vals, infra_vals)
        infra_nonzero = sum(1 for v in infra_vals if v > 0)
        infra_mean    = _mean(infra_vals)

        if   (pr or 0) >  0.1: interp = "EPDO 높을수록 시설 많음 (노출 효과)"
        elif (pr or 0) < -0.1: interp = "EPDO 높을수록 시설 적음 (억제 효과 가능)"
        else:                   interp = "상관 미미"

        corr_result.append({
            "infra_col":         col,
            "pearson_r":         pr,
            "spearman_r":        sr,
            "infra_nonzero_cnt": infra_nonzero,
            "infra_mean":        round(infra_mean, 4),
            "해석":              interp,
        })

    corr_result.sort(key=lambda x: abs(x["pearson_r"] or 0), reverse=True)

    os.makedirs(os.path.dirname(CORR_OUTPUT), exist_ok=True)
    with open(CORR_OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(corr_result[0].keys()))
        w.writeheader()
        w.writerows(corr_result)

    print(f"\n  {'시설물':20s} {'Pearson':>9} {'Spearman':>10}  해석")
    print("  " + "-" * 65)
    for r in corr_result:
        print(f"  {r['infra_col']:20s} {str(r['pearson_r']):>9} {str(r['spearman_r']):>10}  {r['해석']}")

    # ── 분석 2: 고위험 격자 인프라 공백 ──────────────────────────────────────
    print(f"\n[3] 고위험 격자 인프라 공백 추출 (상위 {100 - HIGH_RISK_PERCENTILE}%)...")
    threshold = percentile(epdo_vals, HIGH_RISK_PERCENTILE)
    print(f"    epdo_total 기준값: {threshold:.1f}점")

    infra_means = {
        col: _mean([float(r.get(col, 0) or 0) for r in rows])
        for col in INFRA_COLS
    }

    gap_result = []
    for r in rows:
        epdo = float(r["epdo_total"])
        if epdo < threshold:
            continue

        gaps = []
        for col in INFRA_COLS:
            val = float(r.get(col, 0) or 0)
            if val == 0:
                gaps.append(f"{col}(없음)")
            elif val < infra_means[col] * 0.5:
                gaps.append(f"{col}(부족)")

        gap_result.append({
            "grid_gid":       r["grid_gid"],
            "epdo_total":     epdo,
            "accident_cnt":   int(r["accident_cnt"]),
            "사망_cnt":        int(r["사망_cnt"]),
            "중상_cnt":        int(r["중상_cnt"]),
            "crosswalk_cnt":  int(float(r["crosswalk_cnt"])),
            "cctv_cnt":       int(float(r["cctv_cnt"])),
            "speedbump_cnt":  int(float(r["speedbump_cnt"])),
            "child_zone_cnt": int(float(r["child_zone_cnt"])),
            "gap_cnt":        len(gaps),
            "gap_items":      " | ".join(gaps) if gaps else "-",
        })

    gap_result.sort(key=lambda x: (-x["gap_cnt"], -x["epdo_total"]))

    with open(GAP_OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(gap_result[0].keys()))
        w.writeheader()
        w.writerows(gap_result)

    total_high  = len(gap_result)
    many_gaps   = sum(1 for r in gap_result if r["gap_cnt"] >= len(INFRA_COLS) // 2)
    print(f"    고위험 격자: {total_high:,}개")
    print(f"    시설물 절반 이상 공백: {many_gaps:,}개 ({many_gaps/total_high*100:.1f}%)")

    print(f"\n    공백 심각 상위 10개:")
    print(f"  {'격자ID':12s} {'EPDO':>7} {'사고':>4} {'공백수':>5}  공백 항목")
    print("  " + "-" * 75)
    for r in gap_result[:10]:
        items = r["gap_items"][:50] + ("..." if len(r["gap_items"]) > 50 else "")
        print(f"  {r['grid_gid']:12s} {r['epdo_total']:>7.0f} {r['accident_cnt']:>4}건 {r['gap_cnt']:>5}개  {items}")

    print(f"\n저장: {CORR_OUTPUT}")
    print(f"저장: {GAP_OUTPUT}")
    print("=" * 60)


if __name__ == "__main__":
    main()
