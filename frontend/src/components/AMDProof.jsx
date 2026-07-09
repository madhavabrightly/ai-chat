import { useState, useEffect } from 'react'
import { fetchComputeStatus, healthCheck } from '../api/memoryApi.js'

export default function AMDProof() {
  const [status, setStatus] = useState(null)
  const [online, setOnline] = useState(false)
  const [copied, setCopied] = useState(false)
  const [loading, setLoading] = useState(true)

  function load() {
    setLoading(true)
    healthCheck().then(() => setOnline(true)).catch(() => setOnline(false))
    fetchComputeStatus().then(s => { setStatus(s); setLoading(false) }).catch(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  function copyProof() {
    if (!status) return
    const text = `=== AMD Compute Proof ===
Torch Version: ${status.torch_version}
GPU Available: ${status.cuda_available}
Device: ${status.device}
ROCm/CUDA: ${status.cuda_or_rocm_version}
LLM Model: ${status.llm_model}
Embedding Model: ${status.embedding_model}
Model Cache: ${status.model_cache_path}
ChromaDB Path: ${status.chromadb_path}
Task: ${status.task}
Status: ${online ? 'Live' : 'Offline'}
====================`
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const rows = status ? [
    ['Device', status.device],
    ['Torch Version', status.torch_version],
    ['ROCm / CUDA', status.cuda_or_rocm_version],
    ['GPU Available', status.cuda_available ? '✅ Yes' : '❌ No'],
    ['LLM Model', status.llm_model],
    ['Embedding Model', status.embedding_model],
    ['Model Cache', status.model_cache_path],
    ['ChromaDB Path', status.chromadb_path],
    ['Task', status.task],
    ['Status', online ? '🟢 Live' : '🔴 Offline'],
  ] : []

  return (
    <div className="screen proof-s">
      <div className="proof-head">
        <div>
          <h2>🖥️ AMD Compute Proof</h2>
          <p className="proof-sub">Hardware acceleration and model inference details</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-ghost-sm" onClick={load} disabled={loading}>Refresh</button>
          <button className="btn-primary" onClick={copyProof} disabled={!status}>
            {copied ? '✅ Copied!' : '📋 Copy Proof Text'}
          </button>
        </div>
      </div>

      {loading && <p className="loading-txt">Loading compute status...</p>}

      {!loading && status && (
        <div className="proof-card">
          <div className="proof-badge">AMD Technology</div>
          <div className="proof-grid">
            {rows.map(([l, v]) => (
              <div key={l} className="proof-row">
                <span className="proof-lbl">{l}</span>
                <span className="proof-val">{typeof v === 'boolean' ? (v ? 'Yes' : 'No') : String(v)}</span>
              </div>
            ))}
          </div>
          {status.note && <p className="proof-note">{status.note}</p>}
          <div className="proof-footer">
            <span className="proof-hack-badge">AMD Developer Hackathon 2026</span>
            <span className="proof-hack-badge">Track 3 — Unicorn / Open Innovation</span>
          </div>
        </div>
      )}

      {!loading && !status && (
        <div className="proof-card" style={{ textAlign: 'center', padding: 40 }}>
          <p className="proof-na">Backend offline. Start the server at http://localhost:8000</p>
        </div>
      )}
    </div>
  )
}
