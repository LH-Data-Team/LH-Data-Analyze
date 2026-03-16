
## 실행 순서

COMPAS 환경에서 아래 순서대로 실행합니다.

```
00 → 01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11
```

- STEP 05, 07은 STEP 00 결과에 의존하므로 00 수정 시 05 → 07도 재실행 필요
- STEP 01, 03은 00의 링크매핑 결과에 의존

---
# EPDO 기반 교통사고 위험도 분석 파이프라인

교통사고 이력과 인프라 데이터를 기반으로 격자 단위 종합 위험지수를 산출하고, 시설물 설치 효과를 예측하는 COMPAS 환경용 분석 파이프라인입니다.

---

## 파일 구조

```
LH-Data-Analyze/
├── compas/                          # COMPAS 실행용 Jupyter Notebook
│   ├── COMPAS_00_preprocessing.ipynb
│   ├── COMPAS_01_epdo_score.ipynb
│   ├── COMPAS_02_link_traffic.ipynb
│   ├── COMPAS_03_link_epdo_risk.ipynb
│   ├── COMPAS_04_cause_analysis.ipynb
│   ├── COMPAS_05_grid_epdo_infra.ipynb
│   ├── COMPAS_06_infra_analysis.ipynb
│   ├── COMPAS_07_ml_risk_model.ipynb
│   ├── COMPAS_08_grid_composite_risk.ipynb
│   ├── COMPAS_09_entropy_weight.ipynb
│   ├── COMPAS_10_nb_regression_weight.ipynb
│   └── COMPAS_11_facility_effect.ipynb
├── data/                            # 입력 원시 데이터 
│   
└── output/                          # 각 STEP 산출 결과
    ├── 00_격자별_통합데이터.csv
    ├── 00_교통사고_링크매핑.csv
    ├── 00_링크별_사고집계.csv
    ├── 01_사고별_EPDO점수.csv
    ├── 02_링크별_교통량.csv
    ├── 03_링크별_위험도.csv
    ├── 04_위험도로_원인분석.csv
    ├── 05_격자별_EPDO_인프라통합.csv
    ├── 06_인프라_상관분석.csv
    ├── 07_ML_위험도예측.csv
    ├── 08_격자_종합위험지수.csv
    ├── 08_하남교산_예측위험도.csv
    ├── 09_엔트로피_가중치.csv
    ├── 10_통합가중치_최종.csv
    └── 11_시설물설치_효과예측.csv
```

---


## 분석 파이프라인

### STEP 00 — 원시 데이터 전처리 (`COMPAS_00_preprocessing.ipynb`)

**로직**
- 교통사고(geojson) → sjoin_nearest → 가장 가까운 도로 링크 매핑
- 교통사고(geojson) → sjoin → 격자 할당 (boundary 중복 제거)
- 인프라 CSV 14종 → 좌표 기반 GeoDataFrame 변환 → 격자별 집계
- 과속방지턱 높이: 0·결측 제외 평균(5.86cm)을 기준으로 below/above 분류
- 격자 중복 제거: `drop_duplicates(subset="gid")`

**산출 파일**
| 파일 | 행 수 | 내용 |
|------|-------|------|
| `00_교통사고_링크매핑.csv` | 10,864건 | 사고별 link_id, 심각도, 시간/요일/유형 |
| `00_교통사고_격자매핑.geojson` | 10,864건 | 사고별 grid_gid 할당 |
| `00_격자별_통합데이터.csv` | 99,146개 | 격자별 인프라 13종 집계 |
| `00_링크별_사고집계.csv` | 5,951개 | 링크별 사고 건수 및 uid 목록 |

---

### STEP 01 — 사고별 EPDO 점수 (`COMPAS_01_epdo_score.ipynb`)

**로직**
- EPDO(Equivalent Property Damage Only): 사고 심각도를 재산피해 상당액으로 환산
- 가중치 출처: 이상엽(2019), 대한교통학회지 37(5)

| 심각도 | EPDO 점수 |
|--------|-----------|
| 사망 | 391점 |
| 중상 | 69점 |
| 경상 | 8점 |
| 부상신고 | 6점 |
| 상해없음 | 1점 |

**산출 파일**
| 파일 | 행 수 | 내용 |
|------|-------|------|
| `01_사고별_EPDO점수.csv` | 10,864건 | 사고별 epdo_score 부여 |

---

### STEP 02 — 링크별 교통량 집계 (`COMPAS_02_link_traffic.ipynb`)

**로직**
- v_link_id → link_id 역매핑 (상행/하행 평균 AADT 산출)
- 노출량(Exposure) = AADT × 링크 길이(km)

**산출 파일**
| 파일 | 행 수 | 내용 |
|------|-------|------|
| `02_링크별_교통량.csv` | 23,748개 | link_id, AADT, exposure(대·km/일) |

---

### STEP 03 — 링크별 위험도 산출 (`COMPAS_03_link_epdo_risk.ipynb`)

**로직**
- EPDO Rate = EPDO 합계 / 노출량 × 1,000,000 (백만 대·km당)
- 교통량 미매칭 링크 제외, 사고 3건 미만 링크 제외 후 순위 산출

**산출 파일**
| 파일 | 행 수 | 내용 |
|------|-------|------|
| `03_링크별_위험도.csv` | 5,951개 | epdo_rate, epdo_rank, epdo_total |

---

### STEP 04 — 위험 도로 원인 분석 (`COMPAS_04_cause_analysis.ipynb`)

**로직**
- EPDO Rate 상위 20개 링크 선정 (사고 3건 이상 조건)
- 사고유형, 법규위반, 시간대, 주말비율 패턴 분석

**산출 파일**
| 파일 | 행 수 | 내용 |
|------|-------|------|
| `04_위험도로_원인분석.csv` | 20개 | top_violation, top_acc_type, peak_time, weekend_ratio |

---

### STEP 05 — 격자별 EPDO + 인프라 통합 (`COMPAS_05_grid_epdo_infra.ipynb`)

**로직**
- 사고 격자별 EPDO 합계·평균·건수 및 심각도별 건수 집계
- `00_격자별_통합데이터.csv`의 인프라 컬럼을 LEFT JOIN으로 통합

**산출 파일**
| 파일 | 행 수 | 내용 |
|------|-------|------|
| `05_격자별_EPDO_인프라통합.csv` | 5,723개 | epdo_total, epdo_avg, accident_cnt, 심각도×5, 인프라×9 |

---

### STEP 06 — 인프라 공백 분석 (`COMPAS_06_infra_analysis.ipynb`)

**로직**
- EPDO와 인프라 시설물 간 피어슨·스피어만 상관계수 산출
- 안전시설 6종 기준 공백 판정: 없거나 전체 평균의 50% 미만 → gap_cnt 산출

**산출 파일**
| 파일 | 행 수 | 내용 |
|------|-------|------|
| `06_인프라_상관분석.csv` | 9개 | infra_col, pearson_r, spearman_r, 해석 |

**상관계수 결과 (상위 3개)**
- crosswalk_cnt: +0.146 (노출 효과)
- cctv_cam_cnt: +0.060
- bus_stop_cnt: +0.056

---

### STEP 07 — ML 기반 위험도 예측 (`COMPAS_07_ml_risk_model.ipynb`)

**로직**
- 모델: Random Forest Classifier
- 피처: 인프라 12종 (횡단보도, CCTV, 과속방지턱, 버스정류장 등)
- 고위험 기준: EPDO ≥ 69점 (상위 25%)
- 클래스 불균형 보정: `class_weight='balanced'`
- 전체 99,146개 격자 예측 → 신도시 계획용 사전 위험도 활용

| 지표 | 값 |
|------|----|
| ROC-AUC | 약 0.72 |
| 피처 중요도 1위 | kindergarten_child_cnt |
| 피처 중요도 2위 | cctv_cnt |

**산출 파일**
| 파일 | 행 수 | 내용 |
|------|-------|------|
| `07_ML_위험도예측.csv` | 99,146개 | grid_gid, is_high_risk, risk_prob, predicted_risk |

---

### STEP 08 — 격자 종합위험지수 산출 (`COMPAS_08_grid_composite_risk.ipynb`)

**로직**

6개 보정계수를 곱하여 종합위험지수 산출:

```
composite_risk = EPDO
    × vuln_correction    (노인거주율 + 교통약자유동비)
    × infra_penalty      (1 + gap_cnt / 6)
    × speed_weight       (avg_speed / 60)
    × congestion_factor  (1 + congestion / 100)
    × peak_factor        (취약시간대 인구)
    × weekend_factor     (주말 방문 비율)

entropy_composite_risk = EPDO × (1 + 엔트로피 가중치 적용 보정지수)
```

**위험 라벨 (8가지, 중복 가능)**
- 노인밀집거주: 거주노인율 > 20%
- 교통약자유동多: 교통약자유동비 > 75 퍼센타일
- 주말방문집중: 주말방문비 > 55%
- 통행피크위험: 취약시간 인구 > 중앙값
- 고속도로위험: 평균속도 ≥ 60km/h
- 학교인근: 토지이용 학교 유형
- 주거밀집: 토지이용 주거 유형
- 상업지역: 토지이용 상업 유형

**하남교산 예측**: 4개 신도시 blockType별 평균 entropy_composite_risk로 사전 위험도 예측

**산출 파일**
| 파일 | 행 수 | 내용 |
|------|-------|------|
| `08_격자_종합위험지수.csv` | 5,723개 | composite_risk, entropy_rank, risk_label (31컬럼) |
| `08_하남교산_예측위험도.csv` | 526개 | blockName, pred_risk, risk_grade |

---

### STEP 09 — 엔트로피 가중치 산출 (`COMPAS_09_entropy_weight.ipynb`)

**로직**

엔트로피 가중법 4단계:
1. Min-Max 정규화 (0~1)
2. 각 격자의 인자 비중 산출
3. 엔트로피: `ej = -k × Σ(pij × ln(pij))`
4. 가중치: `wj = (1 - ej) / Σ(1 - ej)`

**산출 결과**
| 순위 | 인자 | 가중치 |
|------|------|--------|
| 1 | elderly_res_ratio (노인거주비율) | 47.53% |
| 2 | vuln_peak_pop (취약시간대인구) | 34.78% |
| 3 | grid_congestion (혼잡도) | 6.87% |
| 4 | grid_avg_speed (평균속도) | 4.85% |
| 5 | weekend_ratio (주말방문비율) | 3.24% |
| 6 | gap_cnt (인프라공백수) | 1.75% |
| 7 | vuln_float_ratio (교통약자유동비율) | 0.67% |

**산출 파일**
| 파일 | 행 수 | 내용 |
|------|-------|------|
| `09_엔트로피_가중치.csv` | 7개 | 인자, 엔트로피, 편차, 가중치(%) |

---

### STEP 10 — 3중 교차검증 통합 가중치 (`COMPAS_10_nb_regression_weight.ipynb`)

**로직**

3가지 방법으로 가중치 산출 후 기하평균으로 통합:
1. **음이항 회귀(NB)**: accident_cnt 예측 시 각 인자의 회귀계수 절댓값 정규화
2. **EPDO 상관계수**: EPDO와의 피어슨 상관계수 절댓값
3. **엔트로피**: STEP 09 결과

**산출 결과**
| 순위 | 인자 | 통합가중치 | 합의도 |
|------|------|-----------|--------|
| 1 | vuln_peak_pop | 51.03% | ★★★ |
| 2 | gap_cnt | 13.18% | ★★ |
| 3 | grid_avg_speed | 8.85% | ★★ |
| 4 | elderly_res_ratio | 8.38% | ★ |
| 5 | grid_congestion | 8.32% | ★ |

**산출 파일**
| 파일 | 행 수 | 내용 |
|------|-------|------|
| `10_통합가중치_최종.csv` | 7개 | NB/Corr/엔트로피 가중치, 통합가중치, 합의도 |

---

### STEP 11 — 시설물 설치 효과 예측 (`COMPAS_11_facility_effect.ipynb`)

**로직**

문헌 기반 시설물별 EPDO 감소율 (보수적 하한값):

| 시설물 | 감소율 | 출처 |
|--------|--------|------|
| 어린이보호구역 | 25% | 행정안전부 (30~40%) |
| 과속방지턱 | 20% | 도로교통공단 (20~30%) |
| 횡단보도 | 15% | 교통안전공단 (15~25%) |
| CCTV 개소 | 12% | 경찰청 (10~20%) |
| 버스정류장 | 8% | — |
| CCTV 대수 | 5% | — |

독립 효과 가정 시 총감소율:
```
총감소율 = 1 - Π(1 - ri)
```

효율성 = EPDO 절감량 / 공백 시설수 (시설물 1개당 기대 효과)

**산출 파일**
| 파일 | 행 수 | 내용 |
|------|-------|------|
| `11_시설물설치_효과예측.csv` | 5,723개 | install_priority, epdo_before/after, epdo_saved, efficiency |

---

## Output 파일 요약

| 파일 | 행 수 | 주요 컬럼 |
|------|-------|----------|
| `00_격자별_통합데이터.csv` | 99,146 | grid_gid, crosswalk_cnt, cctv_cnt, speedbump_cnt 등 13종 |
| `00_교통사고_링크매핑.csv` | 10,864 | uid, link_id, injury_svrity, epdo_score, acc_yr, week_type |
| `00_링크별_사고집계.csv` | 5,951 | link_id, accident_cnt, accident_uids |
| `01_사고별_EPDO점수.csv` | 10,864 | uid, epdo_score (1~391점) |
| `02_링크별_교통량.csv` | 23,748 | link_id, ALL_AADT_total, exposure |
| `03_링크별_위험도.csv` | 5,951 | link_id, epdo_rate, epdo_rank |
| `04_위험도로_원인분석.csv` | 20 | top_violation, top_acc_type, peak_time, weekend_ratio_pct |
| `05_격자별_EPDO_인프라통합.csv` | 5,723 | grid_gid, epdo_total, epdo_avg, accident_cnt, 인프라 9종 |
| `06_인프라_상관분석.csv` | 9 | infra_col, pearson_r, spearman_r, 해석 |
| `07_ML_위험도예측.csv` | 99,146 | grid_gid, is_high_risk, risk_prob, predicted_risk |
| `08_격자_종합위험지수.csv` | 5,723 | composite_risk, entropy_rank, risk_label (31컬럼) |
| `08_하남교산_예측위험도.csv` | 526 | blockName, blockType, pred_risk, risk_grade |
| `09_엔트로피_가중치.csv` | 7 | 인자, 엔트로피, 편차, 가중치(%) |
| `10_통합가중치_최종.csv` | 7 | NB/Corr/엔트로피 가중치, 통합가중치, 합의도 |
| `11_시설물설치_효과예측.csv` | 5,723 | install_priority, epdo_saved, efficiency |

---

## 주요 분석 결과

### 사고 현황
- 총 사고: **10,864건**, 전체 격자 99,146개 중 사고 발생 격자 **5,723개(5.8%)**
- 심각도: 경상 70%, 중상 14%, 부상신고 15%, 사망 <1%

### 링크 위험도
- 사고 발생 링크: **5,951개** / 전체 23,748개
- 상위 20개 위험도로 주요 원인: 안전운전불이행, 신호위반

### 격자 종합위험지수
- 고위험 격자 최우선 인자: **취약시간대 인구(vuln_peak_pop)** — 통합가중치 51%
- 위험 라벨 1위: 노인밀집거주 + 교통약자유동多 복합 격자

### ML 예측
- ROC-AUC: 0.72 / 피처 중요도 1위: 유치원 아동 수

### 시설물 설치 효과
- 5,723개 고위험 격자 대상 설치 시 예상 EPDO 감소: **약 45.7%**
- 효과 1순위 시설: **어린이보호구역(45%)**, 과속방지턱(35%), 횡단보도(12%)
