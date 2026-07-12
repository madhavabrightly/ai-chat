import EmptyState from './EmptyState.jsx'

export default function MemoryRetrievedPanel({ memories }) {
  if (!memories || memories.length === 0) {
    return (
      <div className="panel ret-panel">
        <h3 className="panel-h-title">Retrieved Memories</h3>
        <EmptyState
          icon="📖"
          title="No memories retrieved yet"
          message="Ask a question to retrieve relevant memories."
        />
      </div>
    )
  }

  return (
    <div className="panel ret-panel">
      <h3 className="panel-h-title">Retrieved Memories</h3>
      <div className="ret-list">
        {memories.map((m, i) => (
          <div key={m.memory_id || i} className="ret-item">
            <div className="ret-top">
              <span className="ret-cat">{m.category}</span>
              {m.relevance_score != null && (
                <span className="ret-pct">{(m.relevance_score * 100).toFixed(0)}% match</span>
              )}
            </div>
            <h4 className="ret-name">{m.title}</h4>
            <p className="ret-snip">{m.snippet || m.full_text?.slice(0, 150)}</p>
            {m.emotion && <span className="ret-em">{m.emotion}</span>}
          </div>
        ))}
      </div>
    </div>
  )
}
