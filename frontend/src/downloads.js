export function downloadFile(name, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
export function downloadCsv(name, rows) {
  const cell = value => {
    const text = String(value ?? '')
    const safe = /^[=+@\-\t\r]/.test(text) ? `'${text}` : text
    return `"${safe.replaceAll('"', '""')}"`
  }
  downloadFile(name, '\uFEFF' + rows.map(row => row.map(cell).join(',')).join('\r\n'), 'text/csv;charset=utf-8')
}

export function exportVisits(data, filters) {
  const labels = { day: '일별 추이', week: '주별 추이', month: '월별 추이', facility: '시설', hour: '시간대', weekday: '요일', age: '연령', sex: '성별' }
  const weekdays = ['월', '화', '수', '목', '금', '토', '일']
  const groups = [
    ...Object.entries(data.trends).flatMap(([unit, items]) => items.map(row => [labels[unit] || unit, row.period, '', row.population, ''])),
    ...Object.entries(data.breakdowns).flatMap(([dimension, items]) => items.map(row => [labels[dimension] || dimension, dimension === 'weekday' ? `${weekdays[row.category - 1]}요일` : row.category, '', row.population, ''])),
    ...data.audience.map(row => ['관객 구성', row.age, row.sex, row.population, '']),
    ...data.heatmap.map(row => ['요일×시간', `${weekdays[row.weekday - 1]}요일 ${row.hour}시`, '', row.population, row.observed_days]),
  ]
  downloadCsv('방문집계.csv', [
    ['집계', '항목', '성별', '방문 인구', '관측일 수', '시설', '시작일', '종료일', '연령 조건', '성별 조건'],
    ...groups.map(row => [...row, filters.facility || '전체 시설', data.range.start_date, data.range.end_date, filters.age || '20·30대', filters.sex || '전체']),
  ])
}
