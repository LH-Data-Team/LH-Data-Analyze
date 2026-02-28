"""
교통사고이력 데이터에 고유 식별자(uid) 컬럼을 추가하는 스크립트
- 입력: data/13._교통사고이력.geojson
- 출력: output/13._교통사고이력_uid.geojson
"""

import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_PATH = os.path.join(BASE_DIR, "data", "13._교통사고이력.geojson")
OUTPUT_PATH = os.path.join(BASE_DIR, "output", "13._교통사고이력_uid.geojson")

with open(INPUT_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

for i, feature in enumerate(data["features"], start=1):
    feature["properties"] = {"uid": i, **feature["properties"]}

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"완료: 총 {len(data['features'])}개 행에 uid 부여")
print(f"저장 경로: {OUTPUT_PATH}")
