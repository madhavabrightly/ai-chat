import { useState, useRef } from 'react'

export default function ImportMemory({ onNavigate }) {
  const [file, setFile] = useState(null)
  const [consent, setConsent] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef(null)

  async function handleImport() {
    if (!file || !consent) return
    setLoading(true)
    setError('')
    setMessages([])

    const form = new FormData()
    form.append('file', file)

    try {
      const r = await fetch('/memory/import/preview', { method: 'POST', body: form })
      const data = await r.json()
      if (data.error) {
        setError(data.error)
      } else {
        setSessionId(data.session_id)
        setMessages(data.messages || [])
      }
    } catch (e) {
      setError('Failed to import. Is the backend running?')
    }
    setLoading(false)
  }

  // Speaker colors
  const speakerColors = {}
  const palette = ['#5c2e1a', '#2e7d32', '#a0522d', '#1565c0', '#6a1b9a', '#b8860b', '#c62828', '#00695c']

  function getColor(speaker) {
    if (!speaker) return '#666'
    if (!speakerColors[speaker]) {
      speakerColors[speaker] = palette[Object.keys(speakerColors).length % palette.length]
    }
    return speakerColors[speaker]
  }

  return (
    <div className="screen import-s">
      <div className="import-head">
        <h2>📥 Import Messages</h2>
        <p className="import-sub">Upload a WhatsApp TXT or JSON file to import every message with speaker, date, and exact source.</p>
      </div>

      <div className="import-card">
        <div className="import-section">
          <label className="import-label">Upload File (TXT or JSON)</label>
          <div className="import-upload" onClick={() => fileRef.current?.click()}>
            <input ref={fileRef} type="file" accept=".txt,.json" hidden onChange={e => setFile(e.target.files[0])} />
            {file ? (
              <div className="import-filename">📄 {file.name} ({(file.size / 1024).toFixed(1)} KB)</div>
            ) : (
              <div className="import-placeholder">
                <div className="import-icon">📂</div>
                <div>Drop file here or click to browse</div>
                <div className="import-hint">WhatsApp .txt or .json with messages array</div>
              </div>
            )}
          </div>
        </div>

        <div className="import-section">
          <label className="import-check-label">
            <input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />
            <span>I have permission to import and use this text for a private memory simulation.</span>
          </label>
        </div>

        <button className="btn-primary" onClick={handleImport} disabled={!file || !consent || loading}>
          {loading ? '⏳ Importing...' : '📥 Import Messages'}
        </button>

        {error && <div className="err-banner">{error}</div>}
      </div>

      {/* Per-message display */}
      {messages.length > 0 && (
        <div className="import-message-list">
          <div className="import-ml-head">
            <h3>📋 All Messages ({messages.length})</h3>
            {sessionId && <span className="import-session-badge">Session: {sessionId.slice(0, 20)}...</span>}
          </div>

          <div className="import-ml-table">
            <div className="import-ml-header">
              <span className="iml-col-num">#</span>
              <span className="iml-col-speaker">Speaker</span>
              <span className="iml-col-date">Date</span>
              <span className="iml-col-text">Text</span>
              <span className="iml-col-source">Source Line</span>
            </div>
            {messages.map((msg, i) => (
              <div key={msg.id || i} className="import-ml-row">
                <span className="iml-col-num">{i + 1}</span>
                <span className="iml-col-speaker" style={{ color: getColor(msg.speaker), fontWeight: 600 }}>
                  {msg.speaker || '—'}
                </span>
                <span className="iml-col-date">{msg.date || '—'}</span>
                <span className="iml-col-text">{msg.text}</span>
                <span className="iml-col-source"><code>{msg.exact_source?.slice(0, 80)}{msg.exact_source?.length > 80 ? '...' : ''}</code></span>
              </div>
            ))}
          </div>

          <p className="import-ml-footer">✅ All {messages.length} messages shown with speaker, date, and exact source line.</p>
        </div>
      )}
    </div>
  )
}
