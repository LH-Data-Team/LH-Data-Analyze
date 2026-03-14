import csv, os, json
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
GRID_FILE = os.path.join(BASE, "data", "02._격자_(하남교산).geojson")
ACC_FILE  = os.path.join(BASE, "data", "13._교통사고이력.geojson")
RISK_FILE = os.path.join(BASE, "output", "08_격자_종합위험지수.csv")
OUTPUT    = os.path.join(BASE, "output", "08_하남교산_격자별_사고현황.csv")

EPDO_WEIGHTS = {
    "사망": 391, "중상": 69, "경상": 8,
    "부상신고": 6, "상해없음": 1, "기타불명": 8, "": 0,
}

def point_in_polygon(px, py, polygon):
    """Ray casting algorithm"""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside

print("=" * 60)
print("하남교산 격자별 교통사고 현황 산출")
print("=" * 60)

print("\n[1] 하남교산 격자 로드...")
with open(GRID_FILE, "r", encoding="utf-8") as f:
    grid_data = json.load(f)

grids = []
for feat in grid_data["features"]:
    gid = feat["properties"]["gid"]
    coords = feat["geometry"]["coordinates"][0]
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    grids.append({
        "gid": gid,
        "polygon": coords,
        "xmin": min(xs), "xmax": max(xs),
        "ymin": min(ys), "ymax": max(ys),
    })
print(f"    격자 수: {len(grids)}개")

print("\n[2] 교통사고 로드...")
with open(ACC_FILE, "r", encoding="utf-8") as f:
    acc_data = json.load(f)
accidents = acc_data["features"]
print(f"    사고 수: {len(accidents)}건")

print("\n[3] 공간 조인 중...")
grid_accidents = defaultdict(list)
matched = 0

for acc in accidents:
    coords = acc["geometry"]["coordinates"]
    px, py = coords[0], coords[1]
    props = acc["properties"]
    
    for g in grids:
        if px < g["xmin"] or px > g["xmax"] or py < g["ymin"] or py > g["ymax"]:
            continue
        if point_in_polygon(px, py, g["polygon"]):
            grid_accidents[g["gid"]].append(props)
            matched += 1
            break

print(f"    매칭된 사고: {matched}건")
print(f"    사고 발생 격자: {len(grid_accidents)}개 / 전체 {len(grids)}개")

print("\n[4] 격자별 집계...")
results = []
for g in grids:
    gid = g["gid"]
    accs = grid_accidents.get(gid, [])
    
    acc_cnt = len(accs)
    if acc_cnt == 0:
        continue
    
    death = sum(1 for a in accs if a.get("injury_svrity") == "사망")
    heavy = sum(1 for a in accs if a.get("injury_svrity") == "중상")
    light = sum(1 for a in accs if a.get("injury_svrity") == "경상")
    report = sum(1 for a in accs if a.get("injury_svrity") == "부상신고")
    none_inj = sum(1 for a in accs if a.get("injury_svrity") == "상해없음")
    
    epdo = sum(EPDO_WEIGHTS.get((a.get("injury_svrity") or "").strip(), 0) for a in accs)
    
    results.append({
        "grid_gid": gid,
        "사고건수": acc_cnt,
        "사망": death,
        "중상": heavy,
        "경상": light,
        "부상신고": report,
        "상해없음": none_inj,
        "EPDO점수": epdo,
    })

print("\n[5] entropy_composite_risk + 예측위험도 매칭...")
PRED_FILE = os.path.join(BASE, "output", "08_하남교산_예측위험도.csv")

ecr_map = {}
with open(RISK_FILE, "r", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        ecr_map[row["grid_gid"]] = float(row["entropy_composite_risk"])

pred_map = {}
with open(PRED_FILE, "r", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        pred_map[row["grid_gid"]] = (float(row["pred_risk"]), row["risk_grade"])

print(f"    종합위험지수(4개 신도시): {len(ecr_map)}개")
print(f"    예측위험도(하남교산): {len(pred_map)}개")

Q75 = 111.12
Q25 = 77.38

for r in results:
    gid = r["grid_gid"]
    ecr = ecr_map.get(gid)
    if ecr is not None:
        r["entropy_composite_risk"] = ecr
        if ecr >= Q75:   r["위험등급"] = "고위험"
        elif ecr >= Q25: r["위험등급"] = "중위험"
        else:            r["위험등급"] = "저위험"
        r["출처"] = "종합위험지수"
    elif gid in pred_map:
        pred_risk, pred_grade = pred_map[gid]
        r["entropy_composite_risk"] = pred_risk
        r["위험등급"] = pred_grade
        r["출처"] = "블록유형예측"
    else:
        r["entropy_composite_risk"] = ""
        r["위험등급"] = "미분류"
        r["출처"] = ""

results.sort(key=lambda x: -(x["entropy_composite_risk"] if x["entropy_composite_risk"] != "" else -1))

with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
    headers = ["grid_gid", "사고건수", "사망", "중상", "경상", "부상신고", "상해없음", "EPDO점수", "entropy_composite_risk", "위험등급", "출처"]
    w = csv.DictWriter(f, fieldnames=headers)
    w.writeheader()
    w.writerows(results)

high = sum(1 for r in results if r["위험등급"] == "고위험")
mid = sum(1 for r in results if r["위험등급"] == "중위험")
low = sum(1 for r in results if r["위험등급"] == "저위험")

print(f"\n{'=' * 60}")
print(f"[결과]")
print(f"  사고 발생 격자: {len(results)}개 / 전체 {len(grids)}개")
print(f"  총 사고 건수: {sum(r['사고건수'] for r in results)}건")
print(f"\n  위험등급 분포:")
print(f"    고위험: {high}개 / 중위험: {mid}개 / 저위험: {low}개")
ecr_cnt = sum(1 for r in results if r["출처"] == "종합위험지수")
pred_cnt = sum(1 for r in results if r["출처"] == "블록유형예측")
print(f"    (종합위험지수 매칭: {ecr_cnt}개 / 블록유형예측 매칭: {pred_cnt}개)")

print(f"\n  전체 격자:")
print(f"  {'순위':>4} {'grid_gid':<15} {'사고':>4} {'사망':>4} {'중상':>4} {'EPDO':>6} {'ECR':>8} {'등급':<6} {'출처'}")
print(f"  {'-'*75}")
for i, r in enumerate(results, 1):
    ecr = f"{r['entropy_composite_risk']:.2f}" if r['entropy_composite_risk'] != "" else "N/A"
    print(f"  {i:>4} {r['grid_gid']:<15} {r['사고건수']:>4} {r['사망']:>4} {r['중상']:>4} {r['EPDO점수']:>6} {ecr:>8} {r['위험등급']:<6} {r['출처']}")

print(f"\n  저장: {OUTPUT}")
print(f"{'=' * 60}")
