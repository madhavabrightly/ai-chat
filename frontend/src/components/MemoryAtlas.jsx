import { useState, useEffect } from 'react'
import { fetchMemories } from '../api/memoryApi.js'

const CAT_ICONS = {
  Childhood: '🌳', Family: '👨‍👩‍👧‍👦', Career: '💼',
  Advice: '🌟', 'Faith & Kindness': '🤝', Humor: '😂',
}
const CAT_COLORS = {
  Childhood: '#b8860b', Family: '#8b4513', Career: '#6b3a2a',
  Advice: '#a0522d', 'Faith & Kindness': '#cd853f', Humor: '#d4a76a',
}

export default function MemoryAtlas() {
  const [memories, setMemories] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchMemories()
      .then(d => { setMemories(d.memories || []); setLoading(false) })
      .catch(() => { setError('Could not load memories.'); setLoading(false) })
  }, [])

  const grouped = {}
  memories.forEach(m => {
    if (!grouped[m.category]) grouped[m.category] = []
    grouped[m.category].push(m)
  })

  return (
    <div className="screen atlas-s">
      <div className="atlas-head">
        <h2>🧭 Memory Atlas</h2>
        <p className="atlas-sub">Explore memories across the timeline of a life</p>
      </div>

      {loading && <p className="loading-txt">Loading atlas...</p>}
      {error && <div className="err-banner">{error}</div>}

      {!loading && !error && Object.entries(grouped).map(([cat, mems]) => (
        <div key={cat} className="atlas-era">
          <div className="atlas-era-head">
            <span className="atlas-era-icon">{CAT_ICONS[cat] || '📌'}</span>
            <h3 className="atlas-era-title">{cat}</h3>
            <span className="atlas-era-count">{mems.length} memory{mems.length > 1 ? 'ies' : 'y'}</span>
            <div className="atlas-era-line" style={{ background: CAT_COLORS[cat] || '#b8860b' }} />
          </div>
          <div className="atlas-era-body">
            {mems.map(m => (
              <div key={m.memory_id} className="atlas-card" style={{ borderLeftColor: CAT_COLORS[cat] || '#b8860b' }}>
                <div className="atlas-card-top">
                  <span className="atlas-card-emotion" style={{ background: CAT_COLORS[cat] || '#b8860b' }}>{m.emotion}</span>
                  <span className="atlas-card-title">{m.title}</span>
                </div>
                <p className="atlas-card-text">{m.text}</p>
                <div className="atlas-card-tags">
                  {(m.tags || []).map(t => <span key={t} className="tag-s">{t}</span>)}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
