# 하남교산 시설 추천

이 폴더는 `data/02._격자_(하남교산).geojson`의 `gid`와
`output/13._교통사고_격자매핑.geojson`의 `grid_gid`를 기준으로
조인되는 격자만 대상으로 추천 시설을 산출합니다.
추천 점수는 `10_통합가중치_최종.csv`(엔트로피+음이항+EPDO 통합가중치)를 사용하며,
`어린이보호구역 보강`은 교육시설 반경 조건을 만족할 때만 후보로 허용합니다.

## 입력 데이터

- `data/02._격자_(하남교산).geojson`
- `output/13._교통사고_격자매핑.geojson`
- `02_data_analysis/하남교산시_위험격자.geojson`
- `epdo_analysis/output/10_통합가중치_최종.csv`
- `data/15._학교현황.csv`
- `data/16._유치원현황.csv`

## 실행 방법

```bash
python "12_facility_recommendation/recommend_facility_joined_grids.py"
```

## 출력 파일

- `하남교산_시설추천.csv`
  - 최종 제출용 표 결과
  - 컬럼: `gid`, `추천시설물`
- `하남교산_시설추천.geojson`
  - 지도 시각화용 공간 결과
  - 속성: `gid`, `추천시설물`

## 참고

- 조인되는 고유 격자 수(현재): 41개
- 교육시설 반경 기준: 300m (`학교현황` + `유치원현황`)
