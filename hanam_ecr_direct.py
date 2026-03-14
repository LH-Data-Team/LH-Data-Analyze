"""
41개 하남교산 사고격자에 대해 entropy_composite_risk를 직접 산출.

방법:
1. 08_격자_종합위험지수.csv (1,482개)에서 41개 사고격자 매칭 시도
2. 매칭 안 되는 격자는 00_격자별_통합데이터.csv + 05_격자별_EPDO_인프라통합.csv로
   EPDO × (1 + correction_index) 를 산출 (엔트로피 가중치 기반)
3. 4개 신도시 1,482개 격자의 min/max로 정규화하여 동일 기준 적용
"""
import csv, os

BASE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(BASE, "output")

ECR_FILE     = os.path.join(OUT, "08_격자_종합위험지수.csv")
ACC_FILE     = os.path.join(OUT, "08_하남교산_격자별_사고현황.csv")
PRED_FILE    = os.path.join(OUT, "08_하남교산_예측위험도.csv")
EPDO_FILE    = os.path.join(OUT, "05_격자별_EPDO_인프라통합.csv")
INFRA_FILE   = os.path.join(OUT, "00_격자별_통합데이터.csv")
ENTROPY_FILE = os.path.join(OUT, "09_엔트로피_가중치.csv")
PROPOSAL_FILE = os.path.join(OUT, "08_하남교산_사고격자_시설제안.csv")
OUTPUT       = os.path.join(OUT, "08_하남교산_격자별_사고현황.csv")
PRED_FILE    = os.path.join(OUT, "08_하남교산_예측위험도.csv")

Q75, Q25 = 111.12, 77.38

ENTROPY_FACTORS = [
    "elderly_res_ratio", "vuln_peak_pop", "grid_congestion",
    "grid_avg_speed", "weekend_ratio", "gap_cnt", "vuln_float_ratio"
]

def sf(v, d=0.0):
    try: return float(v or 0)
    except: return d

print("=" * 70)
print("하남교산 41개 사고격자 ECR 직접 산출 (기존 데이터 활용)")
print("=" * 70)

# 1. 엔트로피 가중치 로드
entropy_weights = {}
with open(ENTROPY_FILE, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        entropy_weights[r["인자"]] = sf(r["가중치"])
print(f"\n[1] 엔트로피 가중치: {entropy_weights}")

# 2. 4개 신도시 1,482개 격자 전체 로드 (min/max 기준 + 매칭용)
ecr_data = {}
factor_values = {k: [] for k in ENTROPY_FACTORS}
with open(ECR_FILE, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        ecr_data[r["grid_gid"]] = r
        for k in ENTROPY_FACTORS:
            v = sf(r.get(k))
            if v is not None:
                factor_values[k].append(v)

factor_min = {k: min(vs) for k, vs in factor_values.items() if vs}
factor_max = {k: max(vs) for k, vs in factor_values.items() if vs}
print(f"[2] 4개 신도시 격자: {len(ecr_data)}개 로드")
print(f"    min/max:")
for k in ENTROPY_FACTORS:
    print(f"    {k}: min={factor_min.get(k,0):.4f}, max={factor_max.get(k,0):.4f}")

# 3. 41개 사고격자 로드
acc_grids = []
with open(ACC_FILE, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        acc_grids.append(r)
print(f"\n[3] 사고격자: {len(acc_grids)}개")

# 4. EPDO 통합 데이터 (gap_cnt 등 계산용)
epdo_map = {}
with open(EPDO_FILE, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        epdo_map[r["grid_gid"]] = r

# 5. 인프라 데이터
infra_map = {}
with open(INFRA_FILE, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        infra_map[r["grid_gid"]] = r

# 6. 기존 제안시설 데이터
proposal_map = {}
if os.path.exists(PROPOSAL_FILE):
    with open(PROPOSAL_FILE, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            proposal_map[r["grid_gid"]] = r

# 7. 예측위험도 데이터 (없을 수 있음)
pred_map = {}
if os.path.exists(PRED_FILE):
    with open(PRED_FILE, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            pred_map[r["grid_gid"]] = r

# 8. 각 격자 ECR 산출
INFRA_COLS = ["crosswalk_cnt","child_zone_cnt","school_cnt","kindergarten_cnt","daycare_cnt","bus_stop_cnt","cctv_cnt","cctv_cam_cnt","speedbump_cnt"]

INFRA_NAMES = {
    "crosswalk_cnt": "스마트 횡단보도",
    "child_zone_cnt": "어린이보호구역 보강",
    "school_cnt": "통학로 안전시설",
    "kindergarten_cnt": "유치원 주변 안전시설",
    "daycare_cnt": "어린이집 주변 안전시설",
    "bus_stop_cnt": "버스정류장 연계 보행안전시설",
    "cctv_cnt": "지능형 CCTV",
    "cctv_cam_cnt": "지능형 CCTV",
    "speedbump_cnt": "과속저감 패키지(방지턱+노면표시)",
}

results = []
matched_ecr = 0
calculated_ecr = 0

for a in acc_grids:
    gid = a["grid_gid"]
    
    # 08_격자_종합위험지수.csv에서 직접 매칭
    if gid in ecr_data:
        matched_ecr += 1
        e = ecr_data[gid]
        ecr_val = sf(e["entropy_composite_risk"])
        source = "4개신도시_직접산출"
        
        # 인프라 공백/제안시설 정보
        gap_items = e.get("gap_items", "")
        gap_cnt = int(sf(e.get("gap_cnt", 0)))
        
        inf = infra_map.get(gid, {})
        gaps = []
        proposals = []
        for col in INFRA_COLS:
            v = sf(inf.get(col, e.get(col, 0)))
            if v == 0:
                gaps.append(col)
                if col in INFRA_NAMES:
                    proposals.append(INFRA_NAMES[col])
        
        results.append({
            "grid_gid": gid,
            "사고건수": a["사고건수"],
            "사망": a["사망"],
            "중상": a["중상"],
            "경상": a["경상"],
            "부상신고": a["부상신고"],
            "상해없음": a["상해없음"],
            "EPDO점수": a["EPDO점수"],
            "entropy_composite_risk": ecr_val,
            "위험등급": "",
            "출처": source,
            "핵심_인프라공백": " / ".join(gaps) if gaps else "없음",
            "제안시설": " + ".join(dict.fromkeys(proposals)) if proposals else "해당없음",
        })
    else:
        # 직접 산출: EPDO × (1 + correction_index)
        calculated_ecr += 1
        epdo_total = sf(a["EPDO점수"])
        
        # 인자값 수집
        ep = epdo_map.get(gid, {})
        inf = infra_map.get(gid, {})
        
        # gap_cnt
        gap_cnt = 0
        gaps = []
        proposals = []
        for col in INFRA_COLS:
            v = sf(inf.get(col, ep.get(col, 0)))
            if v == 0:
                gap_cnt += 1
                gaps.append(col)
                if col in INFRA_NAMES:
                    proposals.append(INFRA_NAMES[col])
        
        # 나머지 인자는 4개 신도시 중간값 사용 (데이터 없으므로)
        factor_medians = {}
        for k in ENTROPY_FACTORS:
            vals = sorted(factor_values[k])
            mid = len(vals) // 2
            factor_medians[k] = vals[mid] if vals else 0
        
        raw_vals = {
            "elderly_res_ratio": factor_medians["elderly_res_ratio"],
            "vuln_peak_pop": factor_medians["vuln_peak_pop"],
            "grid_congestion": factor_medians["grid_congestion"],
            "grid_avg_speed": factor_medians["grid_avg_speed"],
            "weekend_ratio": factor_medians["weekend_ratio"],
            "gap_cnt": gap_cnt,
            "vuln_float_ratio": factor_medians["vuln_float_ratio"],
        }
        
        # min-max 정규화 (4개 신도시 기준)
        correction_index = 0
        for k in ENTROPY_FACTORS:
            v = raw_vals[k]
            mn, mx = factor_min.get(k, 0), factor_max.get(k, 0)
            norm = (v - mn) / (mx - mn) if mx > mn else 0.5
            norm = max(0, min(1, norm))
            w = entropy_weights.get(k, 0)
            correction_index += w * norm
        
        ecr_val = round(epdo_total * (1 + correction_index), 2)
        source = "EPDO기반_직접산출"
        
        results.append({
            "grid_gid": gid,
            "사고건수": a["사고건수"],
            "사망": a["사망"],
            "중상": a["중상"],
            "경상": a["경상"],
            "부상신고": a["부상신고"],
            "상해없음": a["상해없음"],
            "EPDO점수": a["EPDO점수"],
            "entropy_composite_risk": ecr_val,
            "위험등급": "",
            "출처": source,
            "핵심_인프라공백": " / ".join(gaps) if gaps else "없음",
            "제안시설": " + ".join(dict.fromkeys(proposals)) if proposals else "해당없음",
        })

# 위험등급 부여
for r in results:
    ecr = r["entropy_composite_risk"]
    if ecr >= Q75:
        r["위험등급"] = "고위험"
    elif ecr >= Q25:
        r["위험등급"] = "중위험"
    else:
        r["위험등급"] = "저위험"

# ECR 기준 내림차순 정렬
results.sort(key=lambda x: -x["entropy_composite_risk"])

# 저장
headers = list(results[0].keys())
with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=headers)
    w.writeheader()
    w.writerows(results)

# 통계
high = sum(1 for r in results if r["위험등급"] == "고위험")
mid = sum(1 for r in results if r["위험등급"] == "중위험")
low = sum(1 for r in results if r["위험등급"] == "저위험")

print(f"\n{'='*70}")
print(f"[결과]")
print(f"  직접 매칭(08_격자_종합위험지수): {matched_ecr}개")
print(f"  EPDO 기반 직접 산출: {calculated_ecr}개")
print(f"  합계: {len(results)}개")
print(f"\n  위험등급 분포:")
print(f"  고위험: {high}개 / 중위험: {mid}개 / 저위험: {low}개")
print(f"\n  Top 10:")
print(f"  {'순위':>4} {'grid_gid':<12} {'EPDO':>6} {'ECR':>10} {'등급':<6} {'출처':<20} {'인프라공백'}")
print(f"  {'-'*90}")
for i, r in enumerate(results[:10], 1):
    print(f"  {i:>4} {r['grid_gid']:<12} {r['EPDO점수']:>6} {r['entropy_composite_risk']:>10} {r['위험등급']:<6} {r['출처']:<20} {r['핵심_인프라공백'][:30]}")

print(f"\n  저장: {OUTPUT}")
print(f"{'='*70}")
