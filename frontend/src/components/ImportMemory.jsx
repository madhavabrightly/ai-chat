import { useState, useRef } from 'react'

export default function ImportMemory({ onNavigate }) {
  const [file, setFile] = useState(null)
  const [mode, setMode] = useState('personal')
  const [consent, setConsent] = useState(false)
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [committed, setCommitted] = useState(false)
  const fileRef = useRef(null)

  async function handleAnalyze() {
    if (!file || !consent) return
    setLoading(true)
    setPreview(null)

    const form = new FormData()
    form.append('file', file)
    form.append('import_mode', mode)

    try {
      const r = await fetch('/memory/import/preview', { method: 'POST', body: form })
      const data = await r.json()
      if (data.error) {
        alert('Error: ' + data.error)
      } else {
        setPreview(data)
      }
    } catch (e) {
      alert('Failed to analyze file. Is the backend running?')
    }
    setLoading(false)
  }

  async function handleCommit() {
    if (!preview) return
    setLoading(true)
    try {
      const r = await fetch('/memory/import/commit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          import_id: preview.import_id,
          memories: preview.preview_memories,
          style_profile: preview.style_profile,
          apply_style_profile: true,
        }),
      })
      const data = await r.json()
      if (data.saved) {
        setCommitted(true)
      } else {
        alert('Error: ' + (data.error || 'Save failed'))
      }
    } catch (e) {
      alert('Failed to save. Is the backend running?')
    }
    setLoading(false)
  }

  const CAT_COLORS = {
    Childhood: '#b8860b', Family: '#8b4513', Career: '#6b3a2a',
    Advice: '#a0522d', 'Faith & Kindness': '#cd853f', Humor: '#d4a76a',
    Relationships: '#b06040', Personal: '#7a6b5a',
  }

  return (
    <div className="screen import-s">
      <div className="import-head">
        <h2>📥 Import Memory</h2>
        <p className="import-sub">Upload a TXT or JSON file to extract memories, detect style, and add to the vault</p>
      </div>

      {!committed ? (
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
                  <div className="import-hint">.txt or .json</div>
                </div>
              )}
            </div>
          </div>

          <div className="import-section">
            <label className="import-label">Import Mode</label>
            <div className="import-modes">
              {[
                { id: 'personal', label: 'Personal memories' },
                { id: 'chat', label: 'Chat conversation' },
                { id: 'diary', label: 'Diary / Journal' },
                { id: 'companion', label: 'Companion style sample' },
              ].map(m => (
                <button key={m.id} className={`chip-f${mode === m.id ? ' chip-f-a' : ''}`} onClick={() => setMode(m.id)}>
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          <div className="import-section">
            <label className="import-check-label">
              <input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} />
              <span>I have permission to import and use this text for a private memory simulation.</span>
            </label>
          </div>

          <button className="btn-primary" onClick={handleAnalyze} disabled={!file || !consent || loading}>
            {loading ? '⏳ Analyzing...' : '🔍 Analyze Memory File'}
          </button>
        </div>
      ) : (
        <div className="import-success">
          <div className="import-success-icon">✅</div>
          <h3>Import Complete!</h3>
          <p>{preview?.memory_count || 0} memories saved to the vault.</p>
          <p>Style profile is active for chat.</p>
          <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
            <button className="btn-primary" onClick={() => onNavigate('chat')}>Chat with this style</button>
            <button className="btn-secondary" onClick={() => onNavigate('vault')}>View Vault</button>
          </div>
        </div>
      )}

      {/* Preview */}
      {preview && !committed && (
        <div className="import-preview">
          <h3>📋 Preview</h3>

          <div className="preview-summary-card">
            <div className="preview-summary-row">
              <span>File</span><span>{preview.file_name}</span>
            </div>
            <div className="preview-summary-row">
              <span>Type</span><span>{preview.file_type}</span>
            </div>
            <div className="preview-summary-row">
              <span>Memory chunks</span><span>{preview.memory_count}</span>
            </div>
            <div className="preview-summary-row">
              <span>Detected tone</span><span style={{ textTransform: 'capitalize' }}>{preview.detected_tone}</span>
            </div>
            <div className="preview-summary-row">
              <span>Emotions</span><span>{preview.detected_emotions?.join(', ')}</span>
            </div>
          </div>

          <div className="preview-style-card">
            <div className="preview-style-title">🎭 Style Profile</div>
            <div className="preview-summary-row">
              <span>Chat style</span><span>{preview.style_profile?.chat_style}</span>
            </div>
            <div className="preview-summary-row">
              <span>Mode</span><span>{preview.style_profile?.companion_mode}</span>
            </div>
          </div>

          <p className="preview-summary">{preview.summary}</p>

          <h4 style={{ marginTop: 16, color: '#5c2e1a' }}>Sample memories ({Math.min(3, preview.preview_memories.length)} shown)</h4>
          <div className="vault-grid" style={{ gridTemplateColumns: '1fr' }}>
            {preview.preview_memories.slice(0, 3).map(m => (
              <div key={m.memory_id} className="mc">
                <div className="mc-bar" style={{ background: CAT_COLORS[m.category] || '#7a6b5a' }} />
                <div className="mc-body">
                  <div className="mc-head">
                    <span className="mc-tag" style={{ background: CAT_COLORS[m.category] || '#7a6b5a' }}>{m.category}</span>
                    <span className="mc-emote">{m.emotion}</span>
                  </div>
                  <h3 className="mc-title">{m.title}</h3>
                  <p className="mc-text">{m.text?.slice(0, 200)}...</p>
                  <div className="mc-tags">
                    {(m.tags || []).slice(0, 4).map(t => <span key={t} className="tag-s">{t}</span>)}
                    <span className="tag-s" style={{ background: '#c9a96e', color: '#fff' }}>imported</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <button className="btn-primary" onClick={handleCommit} disabled={loading} style={{ marginTop: 16 }}>
            {loading ? '⏳ Saving...' : '💾 Save to Memory Vault'}
          </button>
        </div>
      )}

      <div className="import-ethics">
        🛡️ Only import conversations or memories you have permission to use.
        Imported data is used for local/private RAG memory simulation.
        The companion does not become the real person.
        No model training is performed.
      </div>
    </div>
  )
}
