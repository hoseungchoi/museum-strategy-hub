"""Reproduce the facility audit: python -m app.profile_facilities (dev dependencies)."""
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from .database import DATA_DIR
from .main import create_app


def main():
    output = Path(__file__).resolve().parents[2] / 'analysis'
    output.mkdir(exist_ok=True)
    source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(DATA_DIR.glob('*.csv'))}
    reports = []
    with TestClient(create_app()) as client:
        metadata = client.get('/api/metadata').json()
        for facility in metadata['facilities']:
            response = client.get('/api/dashboard', params={'facility': facility})
            response.raise_for_status()
            data = response.json()
            reports.append({'facility': facility, 'range': data['range'], 'summary': data['summary'],
                            'profile': data['facility_profile'], 'strategies': data['strategies'],
                            'diagnostics': data['strategy_diagnostics']})
    artifact = {'source_sha256': source_hashes, 'rule_version': '2.0',
                'scope': 'CSV 전체 기간 · 20/30대 · 전체 성별 · 00~23시', 'facilities': reports}
    (output / 'facility_profiles.json').write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# 시설별 방문 특성·전략 검토 보고서', '',
             f"기간: {metadata['visits']['start_date']} ~ {metadata['visits']['end_date']} · 17개 시설 · 20/30대", '',
             '동일한 판정 규칙으로 시설별 실제 관측값을 비교했습니다. 시설별 전략 개수를 다르게 보이게 하기 위한 하드코딩은 없습니다. 기준은 운영 검토용 휴리스틱이며 통계적 유의성·선호·효과 예측이 아닙니다.', '',
             '## 판정 기준', '',
             '- FST 지원: 양수 합계, 관측 14일 이상, 선택 기간 날짜의 50% 이상 관측.',
             '- 시간 집중: 상위 3시간 비중 ≥30%. 최다 시간이 06~21시이고 새벽 비중 <15%일 때만 안내 운영 검토.',
             '- 집계 점검: 00~05시 비중 ≥15%이면 새벽 운영 대신 집계 범위 검토.',
             '- 관객 집중: 연령·성별 필터가 없는 조건에서 최대 집단 ≥45%.',
             '- 요일 차이: 28일 이상 범위, 평일 10일·주말 4일 이상 관측, 주말/평일 평균 ≥1.30 또는 ≤1/1.30.',
             '- 월 변동: 월 전체가 선택되고 월 날짜의 80% 이상 관측된 월 3개 이상, 월별 관측일 평균 변동계수 ≥0.50.',
             '- 방문 변화: 관측일 평균 ±20% 이상. 직전 동일 길이 기간을 우선 비교하고 두 기간 모두 80% 이상 관측이 필요. 불가능하면 선택 범위 내 최근 연속 6개 완전월을 앞/뒤 3개월로 구분.',
             '- 시설 연계: 역할을 구분한 SECD 최대 상대 비중 ≥50%, 양수 관측 ≥3개월, 특정 한 달 비중 ≤60%. 기준 시설 자료가 없을 때만 상대 시설 역할을 별도로 사용.', '',
             '누락 조합을 0으로 채우지 않습니다. 실제 개관시간·휴관일·공휴일 효과는 확인되지 않습니다. 한 해의 월 변화는 반복 계절성의 증거가 아닙니다. SECD는 FST와 합산·나눗셈하지 않으며 개인 이동 방향·방문 순서를 뜻한다고 단정할 수 없습니다.', '',
             '## 시설별 요약', '',
             '| 시설 | 주말/평일 평균 | 상위3시간 | 최대 관객집단 비중 | 최근 비교 변화 | 제안 수 |',
             '|---|---:|---:|---:|---:|---:|']
    for report in reports:
        p = report['profile']
        ratio = f"{p['weekend_to_weekday_ratio']:.2f}배" if p['weekend_to_weekday_ratio'] is not None else '—'
        delta = p['recent_comparison']['change_percent']
        change = f'{delta:+.1f}%' if delta is not None else '—'
        lines.append(f"| {report['facility']} | {ratio} | {p['top_three_hour_share']:.1%} | {p['top_audience_share']:.1%} | {change} | {len(report['strategies'])} |")
    for report in reports:
        p = report['profile']
        lines.extend(['', f"## {report['facility']}", '',
                      f"방문 인구 합계 {report['summary']['population']:,.2f} · 관측 {p['observed_days']}/{p['calendar_days']}일 · 최대 집단 {p['top_audience']} {p['top_audience_share']:.1%}", ''])
        if not report['strategies']:
            lines.append('운영 조정 기준을 넘는 신호가 확인되지 않아 제안을 자동 생성하지 않았습니다.')
        for strategy in report['strategies']:
            lines.extend([f"### {strategy['goal']} — {strategy['title']}", '',
                          f"근거: {strategy['evidence']}", '', f"실행 검토: {strategy['action']}", ''])
        lines.extend(['| 항목 | 판정 | 측정값과 기준 |', '|---|---|---|'])
        for rule in report['diagnostics']:
            lines.append(f"| {rule['goal']} | {'제안' if rule['matched'] else '보류'} | {rule['reason']} |")
    lines.extend(['', '## 원본 SHA-256', ''])
    lines.extend(f'- `{name}`: `{digest}`' for name, digest in source_hashes.items())
    (output / 'facility_strategy_review.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    for report in reports:
        print(report['facility'], len(report['strategies']), ', '.join(row['goal'] for row in report['strategies']) or '조정 신호 없음')


if __name__ == '__main__':
    main()
