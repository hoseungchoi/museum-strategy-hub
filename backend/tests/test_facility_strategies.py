import csv
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.database import DATA_DIR
from app.main import create_app


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    with TestClient(create_app(db_path=tmp_path_factory.mktemp('profiles') / 'data.duckdb')) as session:
        yield session


def test_facility_profiles_have_distinct_measured_recommendations(client):
    profiles, signatures = {}, set()
    for facility in client.get('/api/metadata').json()['facilities']:
        data = client.get('/api/dashboard', params={'facility': facility}).json()
        profiles[facility] = data
        signatures.add(tuple(sorted(row['id'] for row in data['strategies'])))
        assert {r['code'] for r in data['strategy_diagnostics'] if r['matched']} == {r['id'] for r in data['strategies']}
        assert all(row['trigger'] and row['rule_version'] == '2.0' for row in data['strategies'])
    assert len(signatures) >= 8
    assert profiles['농업박물관']['facility_profile']['weekend_to_weekday_ratio'] == pytest.approx(.42, abs=.01)
    assert profiles['종이나라박물관']['facility_profile']['weekend_to_weekday_ratio'] == pytest.approx(1.50, abs=.01)
    land = profiles['국토발전전시관']
    assert land['facility_profile']['top_audience_share'] > .6
    assert '관객 프로그램' in {r['goal'] for r in land['strategies']}
    assert '관객 프로그램' not in {r['goal'] for r in profiles['국립극장']['strategies']}
    finance = profiles['한국금융사박물관']
    assert '집계 범위 점검' in {r['goal'] for r in finance['strategies']}
    assert '시간대 운영' not in {r['goal'] for r in finance['strategies']}
    bank = profiles['한국은행본점화폐금융박물관']
    assert bank['facility_profile']['relation']['role'] == '상대 시설'
    assert bank['summary']['population'] > 0 and bank['strategies'] == []


def test_quarter_comparison_is_labelled_and_matches_raw_csv(client):
    data = client.get('/api/dashboard', params={'facility': '농업박물관'}).json()
    strategy = next(r for r in data['strategies'] if r['goal'] == '방문 규모 점검')
    assert strategy['chart']['type'] == 'period'
    previous, current = strategy['chart']['items']
    assert current['label'] == '최근 3개월'
    assert (previous['start_date'], previous['end_date']) == ('2025-07-01', '2025-09-30')
    assert (current['start_date'], current['end_date']) == ('2025-10-01', '2025-12-31')
    with next(DATA_DIR.glob('*_FST_TBL.csv')).open(encoding='utf-8-sig') as f:
        raw = [r for r in csv.DictReader(f) if r['FACL_NM'] == '농업박물관']
    for item in (previous, current):
        rows = [r for r in raw if item['start_date'] <= r['P_YYYYMMDD'] <= item['end_date']]
        population = sum(Decimal(r['VIST_POPL_CNT']) for r in rows)
        observed_days = len({r['P_YYYYMMDD'] for r in rows})
        assert Decimal(str(item['population'])) == population
        assert item['observed_days'] == observed_days
        assert item['daily_average'] == pytest.approx(float(population / observed_days), abs=.0051)


def test_limited_audience_and_single_month_do_not_force_strategies(client):
    restricted = client.get('/api/dashboard', params={'facility': '국토발전전시관', 'age': '20대', 'sex': 'F'}).json()
    assert '관객 프로그램' not in {r['goal'] for r in restricted['strategies']}
    single = client.get('/api/dashboard', params={'facility': '국토발전전시관', 'start_date': '2025-06-01', 'end_date': '2025-06-30'}).json()
    assert not {'시설 연계', '월별 운영 준비'} & {r['goal'] for r in single['strategies']}


def test_relation_percentages_are_secd_only_and_sustained(client):
    data = client.get('/api/dashboard', params={'facility': '국토발전전시관'}).json()
    chart = next(r['chart'] for r in data['strategies'] if r['goal'] == '시설 연계')
    with next(DATA_DIR.glob('*_SECD_TBL.csv')).open(encoding='utf-8-sig') as f:
        rows = [r for r in csv.DictReader(f) if r['TRGT_BASE_FACL_NM'] == '국토발전전시관']
    denominator = sum(Decimal(r['VIST_POPL_CNT']) for r in rows)
    for item in chart['items']:
        selected = [r for r in rows if r['TRGT_RLTV_FACL_NM'] == item['label']]
        expected = sum(Decimal(r['VIST_POPL_CNT']) for r in selected)
        assert Decimal(str(item['population'])) == expected
        assert item['share'] == pytest.approx(float(expected / denominator), abs=.000051)
    assert chart['items'][0]['observed_months'] >= 3
    assert chart['items'][0]['max_month_share'] <= .6
