import csv, os

BASE = os.path.dirname(os.path.abspath(__file__))
INFRA_FILE = os.path.join(BASE, "output", "00_격자별_통합데이터.csv")
ACC_FILE = os.path.join(BASE, "output", "08_하남교산_격자별_사고현황.csv")
OUTPUT = os.path.join(BASE, "output", "08_하남교산_사고격자_시설제안.csv")

FACILITY_MAP = {
    "crosswalk_cnt":  "스마트 횡단보도",
    "child_zone_cnt": "어린이보호구역 보강",
    "speedbump_cnt":  "과속저감 패키지(방지턱+노면표시)",
    "cctv_cnt":       "지능형 CCTV",
    "cctv_cam_cnt":   "지능형 CCTV",
    "bus_stop_cnt":   "버스정류장 연계 보행안전시설",
}

INFRA_COLS = ["crosswalk_cnt", "child_zone_cnt", "bus_stop_cnt", "cctv_cnt", "cctv_cam_cnt", "speedbump_cnt"]

acc_gids = []
acc_data = {}
with open(ACC_FILE, "r", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        acc_gids.append(r["grid_gid"])
        acc_data[r["grid_gid"]] = r

infra_data = {}
with open(INFRA_FILE, "r", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["grid_gid"] in acc_data:
            infra_data[r["grid_gid"]] = r

print(f"사고 격자 41개 중 인프라 데이터 매칭: {len(infra_data)}개")

results = []
for gid in acc_gids:
    a = acc_data[gid]
    infra = infra_data.get(gid, {})
    
    gaps = []
    facilities = set()
    for col in INFRA_COLS:
        val = infra.get(col, "")
        try:
            v = float(val)
        except (ValueError, TypeError):
            v = -1
        if v == 0:
            gaps.append(col)
            if col in FACILITY_MAP:
                facilities.add(FACILITY_MAP[col])
    
    results.append({
        "grid_gid": gid,
        "사고건수": a["사고건수"],
        "사망": a["사망"],
        "중상": a["중상"],
        "EPDO점수": a["EPDO점수"],
        "entropy_composite_risk": a["entropy_composite_risk"],
        "위험등급": a["위험등급"],
        "출처": a["출처"],
        "핵심_인프라공백": " / ".join(gaps) if gaps else "없음",
        "제안시설": " + ".join(sorted(facilities)) if facilities else "해당없음",
    })

headers = ["grid_gid", "사고건수", "사망", "중상", "EPDO점수", "entropy_composite_risk", "위험등급", "출처", "핵심_인프라공백", "제안시설"]
with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=headers)
    w.writeheader()
    w.writerows(results)

print(f"\n{'='*80}")
print(f"하남교산 사고 격자 41개 - 인프라공백 & 시설제안")
print(f"{'='*80}")
print(f"\n고위험 격자 ({sum(1 for r in results if r['위험등급']=='고위험')}개):")
print(f"{'순위':>4} {'grid_gid':<12} {'사고':>4} {'중상':>4} {'EPDO':>6} {'ECR':>8} {'인프라공백':<40} {'제안시설'}")
print(f"{'-'*120}")
rank = 1
for r in results:
    if r["위험등급"] == "고위험":
        ecr = r["entropy_composite_risk"] if r["entropy_composite_risk"] else "N/A"
        print(f"{rank:>4} {r['grid_gid']:<12} {r['사고건수']:>4} {r['중상']:>4} {r['EPDO점수']:>6} {ecr:>8} {r['핵심_인프라공백']:<40} {r['제안시설']}")
        rank += 1

print(f"\n중위험 상위 격자 (EPDO 상위 5개):")
print(f"{'순위':>4} {'grid_gid':<12} {'사고':>4} {'중상':>4} {'EPDO':>6} {'ECR':>8} {'인프라공백':<40} {'제안시설'}")
print(f"{'-'*120}")
mid = [r for r in results if r["위험등급"] == "중위험"]
for i, r in enumerate(mid[:5], 1):
    ecr = r["entropy_composite_risk"] if r["entropy_composite_risk"] else "N/A"
    print(f"{i:>4} {r['grid_gid']:<12} {r['사고건수']:>4} {r['중상']:>4} {r['EPDO점수']:>6} {ecr:>8} {r['핵심_인프라공백']:<40} {r['제안시설']}")

print(f"\n저장: {OUTPUT}")
