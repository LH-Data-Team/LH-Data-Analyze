import csv, os

BASE = os.path.dirname(os.path.abspath(__file__))
INPUT = os.path.join(BASE, "output", "08_하남교산_격자_종합위험지수.csv")

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
    for r in csv.DictReader(f):
        gaps, facilities = parse_gaps(r.get("gap_items", ""))
        score = float(r["entropy_composite_risk"])
        if score >= 111.12:
            grade = "고위험"
        elif score >= 77.38:
            grade = "중위험"
        else:
            grade = "저위험"
        rows.append({
            "grid_gid": r["grid_gid"],
            "핵심_인프라공백": " / ".join(gaps) if gaps else "없음",
            "제안시설": " + ".join(facilities) if facilities else "해당없음",
            "위험등급": grade,
        })

with open(INPUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["grid_gid", "핵심_인프라공백", "제안시설", "위험등급"])
    w.writeheader()
    w.writerows(rows)

print(f"{len(rows)}개 격자 → 4컬럼으로 저장 완료: {INPUT}")
