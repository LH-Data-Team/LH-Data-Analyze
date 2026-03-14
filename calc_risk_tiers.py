import csv, os

BASE = os.path.dirname(os.path.abspath(__file__))

# 1) 전체 4개 신도시 격자 (08_격자_종합위험지수.csv)
f1 = os.path.join(BASE, "output", "08_격자_종합위험지수.csv")
rows_all = []
with open(f1, "r", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        rows_all.append(float(r["entropy_composite_risk"]))

rows_all.sort(reverse=True)
n = len(rows_all)
q75 = rows_all[int(n * 0.25)]
q25 = rows_all[int(n * 0.75)]

high = sum(1 for v in rows_all if v >= q75)
mid = sum(1 for v in rows_all if q25 <= v < q75)
low = sum(1 for v in rows_all if v < q25)

print(f"=== 4개 신도시 전체 ({n}개 격자) ===")
print(f"75th percentile (고위험 기준): {q75:.2f}")
print(f"25th percentile (저위험 기준): {q25:.2f}")
print(f"고위험 (>=75th): {high}개")
print(f"중위험 (25th~75th): {mid}개")
print(f"저위험 (<25th): {low}개")
print(f"합계: {high + mid + low}개")

# 2) 하남교산 격자 (08_하남교산_격자_종합위험지수.csv)
f2 = os.path.join(BASE, "output", "08_하남교산_격자_종합위험지수.csv")
rows_h = []
with open(f2, "r", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        rows_h.append(float(r["entropy_composite_risk"]))

rows_h.sort(reverse=True)
nh = len(rows_h)

h_high = sum(1 for v in rows_h if v >= q75)
h_mid = sum(1 for v in rows_h if q25 <= v < q75)
h_low = sum(1 for v in rows_h if v < q25)

print(f"\n=== 하남교산 ({nh}개 격자) ===")
print(f"(전체 기준 75th={q75:.2f}, 25th={q25:.2f} 적용)")
print(f"고위험 (>=75th): {h_high}개")
print(f"중위험 (25th~75th): {h_mid}개")
print(f"저위험 (<25th): {h_low}개")
print(f"합계: {h_high + h_mid + h_low}개")

# 3) 하남 자체 분포 기준
hq75 = rows_h[int(nh * 0.25)]
hq25 = rows_h[int(nh * 0.75)]

hh_high = sum(1 for v in rows_h if v >= hq75)
hh_mid = sum(1 for v in rows_h if hq25 <= v < hq75)
hh_low = sum(1 for v in rows_h if v < hq25)

print(f"\n=== 하남교산 자체 기준 ({nh}개 격자) ===")
print(f"하남 75th percentile: {hq75:.2f}")
print(f"하남 25th percentile: {hq25:.2f}")
print(f"고위험 (>=75th): {hh_high}개")
print(f"중위험 (25th~75th): {hh_mid}개")
print(f"저위험 (<25th): {hh_low}개")
print(f"합계: {hh_high + hh_mid + hh_low}개")
