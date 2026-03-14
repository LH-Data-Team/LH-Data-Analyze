import csv, os

BASE = os.path.dirname(os.path.abspath(__file__))
INPUT = os.path.join(BASE, "output", "08_하남교산_격자_종합위험지수.csv")
OUTPUT = os.path.join(BASE, "output", "08_하남교산_시설제안.csv")

FACILITY_MAP = {
    "crosswalk_cnt":  "스마트 횡단보도",
    "child_zone_cnt": "어린이보호구역 보강",
    "speedbump_cnt":  "과속저감 패키지(방지턱+노면표시)",
    "cctv_cnt":       "지능형 CCTV",
    "cctv_cam_cnt":   "지능형 CCTV",
    "bus_stop_cnt":   "버스정류장 연계 보행안전시설",
}

def parse_gaps(gap_str):
    if not gap_str or gap_str.strip() == "":
        return [], []
    
    items = [g.strip() for g in gap_str.split("|")]
    gaps = []
    facilities = set()
    
    for item in items:
        item = item.strip()
        if not item:
            continue
        
        for key, facility in FACILITY_MAP.items():
            if key in item:
                clean = item.replace("(없음)", "").replace("(부족)", "").strip()
                gaps.append(clean)
                facilities.add(facility)
                break
    
    return gaps, sorted(facilities)

rows = []
with open(INPUT, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    orig_headers = reader.fieldnames
    for r in reader:
        gaps, facilities = parse_gaps(r.get("gap_items", ""))
        r["핵심_인프라공백"] = " / ".join(gaps) if gaps else "없음"
        r["제안시설"] = " + ".join(facilities) if facilities else "해당없음"
        
        score = float(r["entropy_composite_risk"])
        if score >= 111.12:
            r["위험등급"] = "고위험"
        elif score >= 77.38:
            r["위험등급"] = "중위험"
        else:
            r["위험등급"] = "저위험"
        
        rows.append(r)

out_headers = orig_headers + ["핵심_인프라공백", "제안시설", "위험등급"]

with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=out_headers)
    w.writeheader()
    w.writerows(rows)

print(f"총 {len(rows)}개 격자 처리 완료")
print(f"저장: {OUTPUT}")

high = sum(1 for r in rows if r["위험등급"] == "고위험")
mid = sum(1 for r in rows if r["위험등급"] == "중위험")
low = sum(1 for r in rows if r["위험등급"] == "저위험")
print(f"\n위험등급 분포: 고위험 {high} / 중위험 {mid} / 저위험 {low}")

print("\n=== Top 10 미리보기 ===")
print(f"{'순위':>4}  {'grid_gid':<15} {'위험지수':>8} {'등급':<6} {'인프라공백':<40} {'제안시설'}")
print("-" * 130)
for i, r in enumerate(rows[:10], 1):
    print(f"{i:>4}  {r['grid_gid']:<15} {float(r['entropy_composite_risk']):>8.2f} {r['위험등급']:<6} {r['핵심_인프라공백']:<40} {r['제안시설']}")
