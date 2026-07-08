import { useState, useEffect } from 'react'
import { fetchMemories } from '../api/memoryApi.js'
import StatusBadge from './StatusBadge.jsx'
import EmptyState from './EmptyState.jsx'

const CAT_COLORS = {
  Childhood: '#b8860b', Family: '#8b4513', Career: '#6b3a2a',
  Advice: '#a0522d', 'Faith & Kindness': '#cd853f', Humor: '#d4a76a',
}

export default function MemoryVault({ onNavigate, backendOnline }) {
  const [memories, setMemories] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeCat, setActiveCat] = useState('All')
  const [search, setSearch] = useState('')

  function load() {
    setLoading(true)
    setError('')
    fetchMemories()
      .then(d => { setMemories(d.memories || []); setLoading(false) })
      .catch(() => { setError('Could not load memories from backend.'); setLoading(false) })
  }

  useEffect(() => { load() }, [])

  const cats = ['All', ...new Set(memories.map(m => m.category))]

  const filtered = memories.filter(m => {
    if (activeCat !== 'All' && m.category !== activeCat) return false
    if (search.trim()) {
      const q = search.toLowerCase()
      const haystack = [m.title, m.text, m.category, m.emotion, ...(m.tags || [])].join(' ').toLowerCase()
      return haystack.includes(q)
    }
    return true
  })

  return (
    <div className="screen vault-s">
      <div className="vault-head">
        <div className="vault-head-left">
          <h2>Memory Vault</h2>
          <span className="vault-count">{memories.length} memories</span>
          <StatusBadge online={backendOnline} />
        </div>
        <div className="vault-head-right">
          <button className="btn-ghost-sm" onClick={() => onNavigate('home')}>Home</button>
          <button className="btn-ghost-sm" onClick={() => onNavigate('chat')}>Chat</button>
          <button className="btn-ghost-sm" onClick={load} disabled={loading}>Refresh</button>
        </div>
      </div>

      <div className="vault-controls">
        <input
          className="vault-search"
          placeholder="Search memories..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <div className="vault-filters">
          {cats.map(c => (
            <button key={c} className={`chip-f${activeCat === c ? ' chip-f-a' : ''}`} onClick={() => setActiveCat(c)}>
              {c}
            </button>
          ))}
        </div>
      </div>

      {loading && <p className="loading-txt">Loading memories...</p>}
      {error && <div className="err-banner">{error}</div>}

      {!loading && !error && filtered.length === 0 && (
        <EmptyState icon="📚" title="No memories found" message={search ? 'Try a different search term.' : 'No memories match this category.'} />
      )}

      <div className="vault-grid">
        {filtered.map(m => (
          <div key={m.memory_id} className="mc">
            <div className="mc-bar" style={{ background: CAT_COLORS[m.category] || '#b8860b' }} />
            <div className="mc-body">
              <div className="mc-head">
                <span className="mc-tag" style={{ background: CAT_COLORS[m.category] || '#b8860b' }}>{m.category}</span>
                <span className="mc-emote">{m.emotion}</span>
              </div>
              <h3 className="mc-title">{m.title}</h3>
              <p className="mc-text">{m.text}</p>
              <div className="mc-tags">
                {(m.tags || []).map(t => <span key={t} className="tag-s">{t}</span>)}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
