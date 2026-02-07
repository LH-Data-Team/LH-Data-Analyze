import pandas as pd
import os

# 현재 스크립트 기준 경로
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 파일 불러오기
df11 = pd.read_csv(os.path.join(BASE_DIR, "11._혼잡빈도강도.csv"), encoding="utf-8-sig")
df12 = pd.read_csv(os.path.join(BASE_DIR, "12._혼잡시간강도.csv"), encoding="utf-8-sig")

# v_link_id 집합 생성
set11 = set(df11["v_link_id"].dropna())
set12 = set(df12["v_link_id"].dropna())

# 전체 동일 여부
if set11 == set12:
    print("✅ 11번 파일과 12번 파일의 v_link_id가 완전히 동일합니다.")
else:
    print("❌ v_link_id가 완전히 동일하지 않습니다.")

    # 11에는 있고 12에는 없는 ID
    only_in_11 = set11 - set12
    # 12에는 있고 11에는 없는 ID
    only_in_12 = set12 - set11

    print(f"🔸 11번에만 있는 v_link_id 개수: {len(only_in_11)}")
    print(f"🔸 12번에만 있는 v_link_id 개수: {len(only_in_12)}")

    # 필요하면 일부 출력
    print("\n예시 (11번에만 있는 ID):", list(only_in_11)[:5])
    print("예시 (12번에만 있는 ID):", list(only_in_12)[:5])
