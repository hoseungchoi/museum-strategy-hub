# Culture+ 분석 백엔드

Python 3.9 이상, FastAPI, DuckDB로 구성합니다. 현재 제공된 CSV 두 개만 사용하며 외부 API나 GPT API 키는 필요하지 않습니다.

## 설치·실행

저장소 루트에서:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

- API 문서: http://127.0.0.1:8000/docs
- 상태 확인: http://127.0.0.1:8000/api/health
- 개발 React 허용 출처: localhost:5173, 127.0.0.1:5173
- 프런트엔드는 실제 API에 연결되어 있으며 Vite 개발 프록시를 통해 호출합니다.

첫 시작 시 `data/*_FST_TBL.csv`, `data/*_SECD_TBL.csv`를 읽어 `backend/storage/museum.duckdb`를 생성합니다. 각 패턴은 정확히 한 파일이어야 합니다. 날짜·시간·인구 자료형과 성별 코드를 정리하고 필수값, 음수, 차원 중복 등을 검사합니다. 원본은 수정하지 않습니다. 파일 내용의 해시가 같으면 재적재하지 않고, 변경되면 트랜잭션으로 다시 적재합니다. CSV 변경 반영에는 서버 재시작이 필요합니다.

로컬 단일 서버 프로세스를 기준으로 합니다. 여러 worker의 동시 적재나 쓰기 서비스용 구성이 아닙니다.

## API

| 경로 | 내용 |
|---|---|
| `/api/dashboard` | 공통 필터의 요약·분포·관객 구성·추이·기간 비교·규칙형 전략 |
| `/api/metadata` | 시설 목록, 날짜 범위, 행 수, 필터 값 |
| `/api/visits/summary` | 방문 인구 합계, 관측 행·일 수 |
| `/api/visits/trend` | 일·주·월 추이 (`granularity=day/week/month`) |
| `/api/visits/breakdown` | 시설·시간·성별·연령·요일 집계 (`dimension=facility/hour/sex/age/weekday`) |
| `/api/relations` | 월·기준 시설·상대 시설별 SECD 합계 |
| `/api/quality` | 전체 행 수, 0값 행 수, 합계, 최댓값 |

방문 API 공통 필터: `start_date`, `end_date` (YYYY-MM-DD, 양끝 포함), `facility`, `sex` (F/M), `age` (20대/30대), `hour_start`, `hour_end` (0~23, 양끝 포함). 자정을 넘기는 시간 범위는 두 번 조회합니다.

시설 간 API 필터: `start_month`, `end_month` (2025-MM, 양끝 포함), `base_facility`, `related_facility`, `sex`, `age`. 일·시간 필터를 적용하지 않습니다.

```sh
curl 'http://127.0.0.1:8000/api/visits/trend?granularity=month&sex=F'
```

## 해석 기준

- 모든 결과는 20·30대에 한정됩니다. 고유 방문자 수가 아닙니다.
- 인구는 DB에서 DECIMAL(18,2)로 집계하고 JSON에서는 숫자로 제공합니다.
- 없는 조합·기간을 0으로 채우지 않습니다. `observed_rows`, `observed_days`는 실제 행이 있는 범위입니다. 빈 조회는 합계 0, 관측 수 0으로 반환합니다.
- 주별 기간 표시는 월요일 시작일이며, 조회 경계의 첫·마지막 주는 부분 주일 수 있습니다. 요일은 월요일 1~일요일 7입니다.
- SECD 기준·상대 시설은 실제 이동 방향을 의미한다고 단정하지 않습니다. FST와의 비율, 개인별 경로, 체류시간, 재방문율은 제공하지 않습니다.
- `/api/dashboard`는 직전 동일 길이 기간이 CSV 범위 내일 때 비교합니다. 이전 관측 행이 없거나 합계가 0이면 증감률은 제공하지 않습니다.
- 구성비는 같은 조건의 합계를 분모로 계산합니다. 전략 규칙 v2.0은 시설별 집중도·요일 차이·월 변동·방문 변화·연계 지속성을 평가해 기준에 해당하는 항목만 제안합니다. 운영 검토용 휴리스틱이며 통계적 유의성·인과관계·기대 효과의 예측이 아닙니다.
- `/api/dashboard`의 `heatmap`은 같은 필터로 요일(월=1~일=7)·시간별 인구 합계, 관측 행 수, 관측일 수를 반환합니다. 없는 조합은 행을 생성하지 않으며 요일별 일수 보정 없이 합산합니다.
- `heatmap_audience`는 같은 조건의 요일·시간·연령·성별 인구 합계입니다. 프런트엔드가 이를 이용해 히트맵 상세 패널을 표시합니다.
- FST 기본 지원은 양수 합계·관측 14일·날짜의 50% 이상 관측입니다. 시간 집중은 상위 3시간 비중 ≥30%, 새벽 비중 <15%이며 최다 시간이 06~21시일 때 검토합니다. 새벽 비중 ≥15%이면 운영 확장 대신 집계 범위 점검을 제안합니다. 실제 개관시간을 뜻하지 않습니다.
- 관객 집중은 연령·성별 필터가 없고 최대 집단 ≥45%일 때만 제안합니다. 평일·주말은 28일 이상 범위에서 평일 10일/주말 4일 이상 관측되고 평균 비율이 ≥1.30 또는 ≤1/1.30일 때 제안합니다. 월별 준비는 날짜의 80% 이상 관측된 완전월 3개 이상에서 평균 변동계수 ≥0.50일 때 제안합니다.
- 방문 변화는 관측일 평균이 ±20% 이상 달라질 때 제안합니다. 직전 동일 길이 기간을 우선하며 양쪽 날짜의 80% 이상 관측이 필요합니다. 비교가 불가능하면 선택 범위 안의 최근 연속 6개 완전월을 앞/뒤 3개월로 나누고 해당 날짜를 명시합니다. 기존 KPI의 직전 동일 기간 합계 비교와 별도 지표입니다.
- 시설 연계는 SECD 최대 상대 비중 ≥50%, 양수 관측 ≥3개월, 특정 한 달 집중 ≤60%일 때 제안합니다. 기준 역할에 자료가 없을 때만 상대 역할로 별도 조회합니다. 역할을 합산하지 않습니다. 비중은 같은 역할의 시설 쌍 집계 합을 분모로 하며 FST를 사용하지 않습니다. 월 전체 집계 범위를 명시합니다.
- `facility_profile`에 측정값, `strategy_diagnostics`에 7개 규칙의 제안/보류 이유, `strategy_rule_version`에 버전을 제공합니다. `strategies[].chart`에는 `hours`, `period`, `day_types`, `monthly`, `relations` 유형과 근거를 담습니다. 자료 부족과 충분히 관측됐지만 기준을 넘지 않은 경우를 구분합니다.
- 전체 17개 시설의 재현 가능한 분석은 개발 의존성 설치 후 `cd backend`에서 `.venv/bin/python -m app.profile_facilities`로 생성합니다. [시설별 상세 보고서](../analysis/facility_strategy_review.md)와 [측정값 JSON](../analysis/facility_profiles.json)에 원본 SHA-256, 전체 기간의 지표·전략·보류 이유를 보관합니다. 화면의 기간·관객 필터를 바꾸면 해당 조건으로 다시 계산하므로 보고서와 달라질 수 있습니다.
- 실제 인증은 없습니다. 개발용 로컬 주소에 바인딩합니다.

## 검증

```sh
backend/.venv/bin/pip install -r backend/requirements-dev.txt
cd backend
.venv/bin/python -m pytest -q
```

원본 CSV 합계 일치, 복합 필터, 집계 보존, 시설 쌍 조회, 잘못된 조건, 빈 결과, 병렬 읽기와 재시작을 확인합니다.
