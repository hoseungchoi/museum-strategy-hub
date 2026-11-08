import { useState } from 'react'
import { Icon } from './ui'

const format = value => Number(value).toLocaleString('ko-KR', { maximumFractionDigits: 0 })
const segments = [
  { age: '20대', sex: 'F', name: '20대 여성', color: '#176b68' },
  { age: '20대', sex: 'M', name: '20대 남성', color: '#5688a8' },
  { age: '30대', sex: 'F', name: '30대 여성', color: '#9b7440' },
  { age: '30대', sex: 'M', name: '30대 남성', color: '#7964a0' },
]

export default function AudienceDonut({ data }) {
  const [picked, setPicked] = useState(null)
  const [hovered, setHovered] = useState(null)
  const total = Number(data.summary.population)
  const groups = segments.map(segment => ({ ...segment, row: data.audience.find(row => row.age === segment.age && row.sex === segment.sex) }))
  const active = hovered ?? picked
  const selected = active == null ? null : groups[active]
  const circumference = 2 * Math.PI * 126
  const arcs = groups.map((group, index) => {
    const size = total > 0 ? Number(group.row?.population || 0) / total * circumference : 0
    const offset = total > 0 ? groups.slice(0, index).reduce((sum, item) => sum + Number(item.row?.population || 0), 0) / total * circumference : 0
    return { ...group, offset, size }
  })
  const select = index => setPicked(current => current === index ? null : index)
  return <section className="home-overview audience-overview" aria-label="연령 성별 방문 구성">
    <div className="overview-heading"><div><span className="eyebrow">AUDIENCE OVERVIEW</span><h2>연령·성별 방문 구성</h2></div><span className="overview-period">20·30대 방문 구성</span></div>
    <div className="overview-body"><div className="audience-orbit">
      <div className="orbit-ring" onMouseLeave={() => setHovered(null)}>
        <svg viewBox="0 0 340 340" role="group" aria-label="연령·성별 방문 비중 도넛" className="home-donut-svg">
          <circle cx="170" cy="170" r="151" fill="none" stroke="#dce7e1" strokeWidth="1" strokeDasharray="2 7"/>
          <circle cx="170" cy="170" r="126" fill="none" stroke="#e6eeea" strokeWidth="44"/>
          {arcs.map((arc, index) => arc.size > 0 && <circle key={arc.name} cx="170" cy="170" r="126" fill="none" stroke={arc.color} strokeWidth={active === index ? 53 : 44} strokeDasharray={`${Math.max(0.01, arc.size - Math.min(5, arc.size * .12))} ${circumference}`} strokeDashoffset={-arc.offset} transform="rotate(-90 170 170)" className={`orbit-segment ${active != null && active !== index ? 'muted-segment' : ''}`} role="button" tabIndex="0" aria-label={`${arc.name}, ${format(arc.row.population)}명, ${(arc.row.population / total * 100).toFixed(1)}%`} aria-pressed={picked === index} onMouseEnter={() => setHovered(index)} onFocus={() => setHovered(index)} onBlur={() => setHovered(null)} onClick={() => select(index)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); select(index) } }}><title>{arc.name}: {format(arc.row.population)}명</title></circle>)}
        </svg>
        <div className="orbit-center" aria-live="polite"><span className="center-label">{selected ? selected.name : '방문 인구 합계'}</span><strong className="audience-total-value">{format(selected?.row?.population ?? total)}</strong><span className="center-unit">명</span><b style={{ color: selected?.color || '#176b68' }}>{selected && total > 0 ? `${(selected.row.population / total * 100).toFixed(1)}%` : '선택 범위 전체'}</b></div>
      </div>
      <div className="orbit-caption"><span>조각을 선택하면 상세 비중을 볼 수 있어요</span><button className="orbit-reset" onClick={() => { setPicked(null); setHovered(null) }} disabled={active == null}>전체 보기 <Icon name="arrow" size={13}/></button></div>
    </div>
    <div className="overview-sidebar">
    <div className="orbit-legend" aria-label="관객 집단 선택">{groups.map((group, index) => <button key={group.name} className={active === index ? 'selected' : ''} disabled={!group.row} aria-pressed={picked === index} onMouseEnter={() => setHovered(index)} onMouseLeave={() => setHovered(null)} onFocus={() => setHovered(index)} onBlur={() => setHovered(null)} onClick={() => select(index)}><i style={{ background: group.color }}/><span>{group.name}</span><b>{group.row ? `${format(group.row.population)}명` : '관측 없음'}</b><small>{group.row && total > 0 ? `${(group.row.population / total * 100).toFixed(1)}%` : '—'}</small></button>)}</div>
    </div></div>
  </section>
}
