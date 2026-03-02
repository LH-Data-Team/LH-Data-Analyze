"""
STEP 07 - 링크 위험도 보강: 평균속도 + 혼잡강도
- 입력: epdo_analysis/output/03_링크별_위험도.csv
        data/09._평균속도.csv          (v_link_id, timeslot, velocity_AVRG)
        data/11._혼잡빈도강도.csv       (v_link_id, FRIN_CG)
        data/12._혼잡시간강도.csv       (v_link_id, TI_CG)
        data/08.상세도로망_네트워크.geojson (v_link_id → link_id 매핑)
- 출력: epdo_analysis/output/07_링크_속도혼잡_보강.csv

속도 보정 위험도:
  speed_adjusted_rate = epdo_rate × (avg_speed / 60.0)
  - 60km/h 기준: 초과할수록 보행자 치사율 급증 (교통안전공단 기준)
  - avg_speed < 60이면 가중치 < 1 (상대적으로 낮게 보정)

혼잡 위험도:
  congestion_risk = FRIN_CG × TI_CG / 100
  - FRIN: 혼잡빈도강도(얼마나 자주 막히는가, 0~100)
  - TI  : 혼잡시간강도(막혔을 때 얼마나 심한가, 0~100)

종합 보정 위험도:
  enhanced_rate = epdo_rate × speed_weight × (1 + congestion_weight)
"""

import csv
import json
import os
from collections import defaultdict

BASE_DIR      = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RISK_FILE     = os.path.join(BASE_DIR, "epdo_analysis", "output", "03_링크별_위험도.csv")
SPEED_FILE    = os.path.join(BASE_DIR, "data", "09._평균속도.csv")
FRIN_FILE     = os.path.join(BASE_DIR, "data", "11._혼잡빈도강도.csv")
TI_FILE       = os.path.join(BASE_DIR, "data", "12._혼잡시간강도.csv")
ROAD_FILE     = os.path.join(BASE_DIR, "data", "08.상세도로망_네트워크.geojson")
OUTPUT_PATH   = os.path.join(BASE_DIR, "epdo_analysis", "output", "07_링크_속도혼잡_보강.csv")

SPEED_BASE    = 60.0   # km/h 기준 (보행자 치사율 급증 기준)


def build_vlink_to_link(road_file):
    """v_link_id(상행/하행) → link_id 매핑 딕셔너리 생성 (STEP 02와 동일 로직)"""
    with open(road_file, "r", encoding="utf-8") as f:
        road = json.load(f)
    mapping = {}
    for feat in road["features"]:
        p   = feat["properties"]
        lid = str(p["link_id"])
        for key in ("up_v_link", "dw_v_link"):
            v = p.get(key)
            if v:
                mapping[str(v)] = lid
    return mapping


def main():
    print("=" * 60)
    print("STEP 07 - 링크 위험도 보강: 속도 + 혼잡강도")
    print("=" * 60)

    # 1. v_link_id → link_id 매핑
    print("\n[1] 도로망 매핑 로드 중...")
    vlink_to_link = build_vlink_to_link(ROAD_FILE)
    print(f"    v_link → link 매핑 수: {len(vlink_to_link):,}")

    # 2. 평균속도 집계 (timeslot별 전체 평균, 전 시간대 합산)
    print("\n[2] 평균속도 로드 중...")
    speed_sum   = defaultdict(float)
    speed_cnt   = defaultdict(int)
    peak_speed  = defaultdict(list)   # 07~09시(출근), 16~19시(하교/퇴근)

    with open(SPEED_FILE, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            vid  = row["v_link_id"]
            lid  = vlink_to_link.get(vid)
            if not lid:
                continue
            try:
                slot = int(row["timeslot"])
                spd  = float(row["velocity_AVRG"])
            except (ValueError, KeyError):
                continue
            speed_sum[lid] += spd
            speed_cnt[lid] += 1
            if slot in (7, 8, 9, 16, 17, 18, 19):   # 교통약자 위험 시간대
                peak_speed[lid].append(spd)

    link_avg_speed  = {
        lid: round(speed_sum[lid] / speed_cnt[lid], 2)
        for lid in speed_sum
    }
    link_peak_speed = {
        lid: round(sum(v) / len(v), 2)
        for lid, v in peak_speed.items() if v
    }
    print(f"    속도 매칭 링크: {len(link_avg_speed):,}개")

    # 3. 혼잡빈도강도 (FRIN_CG)
    print("\n[3] 혼잡빈도강도 로드 중...")
    frin_by_link = defaultdict(list)
    with open(FRIN_FILE, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            vid = row["v_link_id"]
            lid = vlink_to_link.get(vid)
            if lid:
                try:
                    frin_by_link[lid].append(float(row["FRIN_CG"]))
                except ValueError:
                    pass
    link_frin = {lid: round(sum(v)/len(v), 4) for lid, v in frin_by_link.items()}
    print(f"    혼잡빈도 매칭 링크: {len(link_frin):,}개")

    # 4. 혼잡시간강도 (TI_CG)
    print("\n[4] 혼잡시간강도 로드 중...")
    ti_by_link = defaultdict(list)
    with open(TI_FILE, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            vid = row["v_link_id"]
            lid = vlink_to_link.get(vid)
            if lid:
                try:
                    ti_by_link[lid].append(float(row["TI_CG"]))
                except ValueError:
                    pass
    link_ti = {lid: round(sum(v)/len(v), 4) for lid, v in ti_by_link.items()}
    print(f"    혼잡시간 매칭 링크: {len(link_ti):,}개")

    # 5. 기존 링크 위험도 로드
    print("\n[5] 기존 링크 위험도 로드 중...")
    risk_rows = []
    with open(RISK_FILE, "r", encoding="utf-8-sig") as f:
        risk_rows = list(csv.DictReader(f))
    print(f"    링크 수: {len(risk_rows):,}개")

    # 6. 보강 계산
    print("\n[6] 속도·혼잡 보강 위험도 산출 중...")
    result = []
    matched_speed = matched_frin = matched_ti = 0

    for r in risk_rows:
        lid        = r["link_id"]
        epdo_rate  = r["epdo_rate"]

        avg_spd    = link_avg_speed.get(lid)
        peak_spd   = link_peak_speed.get(lid)
        frin       = link_frin.get(lid)
        ti         = link_ti.get(lid)

        if avg_spd is not None:
            matched_speed += 1
        if frin is not None:
            matched_frin += 1
        if ti is not None:
            matched_ti += 1

        # 속도 가중치: avg_speed / 60 (60km/h 미만이면 1 미만)
        speed_weight = round(avg_spd / SPEED_BASE, 4) if avg_spd is not None else None

        # 혼잡 위험도: FRIN × TI / 100 (두 값 모두 있을 때만)
        congestion_risk = None
        if frin is not None and ti is not None:
            congestion_risk = round(frin * ti / 100, 4)

        # 종합 보정 위험도 (epdo_rate × 속도 × (1 + 혼잡))
        enhanced_rate = None
        if epdo_rate and epdo_rate != "" and speed_weight is not None:
            base = float(epdo_rate)
            cong_factor = (1 + congestion_risk / 100) if congestion_risk else 1.0
            enhanced_rate = round(base * speed_weight * cong_factor, 4)

        # 분류 레이블
        if avg_spd is not None:
            if avg_spd >= 80:
                speed_label = "고속(80+)"
            elif avg_spd >= 60:
                speed_label = "준고속(60~80)"
            elif avg_spd >= 40:
                speed_label = "중속(40~60)"
            else:
                speed_label = "저속(40미만)"
        else:
            speed_label = ""

        result.append({
            "link_id":          lid,
            "road_name":        r["road_name"],
            "road_rank":        r["road_rank"],
            "accident_cnt":     r["accident_cnt"],
            "epdo_total":       r["epdo_total"],
            "epdo_rate":        epdo_rate,
            "epdo_rank":        r["epdo_rank"],
            # 속도
            "avg_speed":        avg_spd if avg_spd is not None else "",
            "peak_speed":       peak_spd if peak_spd is not None else "",
            "speed_label":      speed_label,
            "speed_weight":     speed_weight if speed_weight is not None else "",
            # 혼잡
            "frin_cg":          frin if frin is not None else "",
            "ti_cg":            ti if ti is not None else "",
            "congestion_risk":  congestion_risk if congestion_risk is not None else "",
            # 보정 위험도
            "enhanced_rate":    enhanced_rate if enhanced_rate is not None else "",
        })

    # 보정 위험도 기준 재정렬 + 순위 부여
    result.sort(key=lambda x: (x["enhanced_rate"] == "", -(x["enhanced_rate"] or 0)))
    rank = 1
    for r in result:
        if r["enhanced_rate"] != "":
            r["enhanced_rank"] = rank
            rank += 1
        else:
            r["enhanced_rank"] = ""

    # 7. 저장
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    cols = list(result[0].keys()) + ["enhanced_rank"]
    cols = list(dict.fromkeys(cols))   # 중복 제거
    with open(OUTPUT_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(result)

    print(f"\n[결과]")
    print(f"    전체 링크: {len(result):,}개")
    print(f"    속도 매칭: {matched_speed:,}개 ({matched_speed/len(result)*100:.1f}%)")
    print(f"    혼잡빈도 매칭: {matched_frin:,}개 ({matched_frin/len(result)*100:.1f}%)")
    print(f"    혼잡시간 매칭: {matched_ti:,}개 ({matched_ti/len(result)*100:.1f}%)")

    enh = [r for r in result if r["enhanced_rate"] != ""]
    print(f"    종합보정 위험도 산출: {len(enh):,}개")
    print(f"\n    보정 위험도 상위 10개:")
    print(f"  {'순위':>4} {'도로명':15s} {'원래rate':>12} {'속도':>6} {'혼잡':>6} {'보정rate':>14}")
    print("  " + "-" * 70)
    for r in result[:10]:
        if r["enhanced_rate"] == "":
            continue
        print(f"  {r['enhanced_rank']:>4} {str(r['road_name']):15s} "
              f"{float(r['epdo_rate']):>12.1f} "
              f"{str(r['avg_speed']):>6} "
              f"{str(r['congestion_risk']):>6} "
              f"{float(r['enhanced_rate']):>14.1f}")

    print(f"\n저장: {OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
