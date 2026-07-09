import GlowingOrb from './GlowingOrb.jsx'
import StatusBadge from './StatusBadge.jsx'

export default function HomeScreen({ onNavigate, backendOnline, computeStatus, refreshStatus }) {
  const pipeline = ['Memories', 'Embeddings', 'ChromaDB', 'Retrieved', 'LLM Answer']

  return (
    <div className="screen home">
      <div className="home-card">
        <div className="home-hero">
          <GlowingOrb pulsing={false} size={90} />
          <h1 className="home-title">Memory Twin AI</h1>
          <p className="home-sub">
            Consent-based AI memory simulation using RAG, ChromaDB, Qwen embeddings, and Qwen LLM.
          </p>
        </div>

        <div className="pipeline-row">
          {pipeline.map((s, i) => (
            <span key={s} className="pipe-item">
              <span className="pipe-num">{i + 1}</span>
              <span>{s}</span>
            </span>
          ))}
        </div>

        <div className="home-status-row">
          <div className="status-group">
            <span className="status-label">Backend</span>
            <StatusBadge online={backendOnline} />
          </div>
          {backendOnline === false && (
            <p className="home-offline-msg">
              Backend offline. Start FastAPI at http://localhost:8000.
            </p>
          )}
          {computeStatus && backendOnline && (
            <div className="compute-preview">
              <span className="cp-chip">{computeStatus.device}</span>
              <span className="cp-chip">{computeStatus.llm_model}</span>
              <span className="cp-chip">{computeStatus.embedding_model}</span>
              <span className="cp-chip">Torch {computeStatus.torch_version}</span>
            </div>
          )}
        </div>

        {/* Consent & Safety Guardrail */}
        <div className="consent-panel">
          <div className="consent-icon">🛡️</div>
          <div className="consent-body">
            <div className="consent-title">Ethical Guardrail — Consent-Based Memory Simulation</div>
            <p className="consent-text">
              Memory Twin AI is a <strong>consent-based digital memory simulation</strong>.
              It does <strong>not claim to be a real person</strong>.
              It answers <strong>only from stored fictional memories</strong>.
              No real personal data is used. All memories are hand-authored fictional examples
              demonstrating the architecture.
            </p>
          </div>
        </div>

        <div className="home-actions">
          <button className="btn-primary" onClick={() => onNavigate('chat')}>
            Start Chat
          </button>
          <button className="btn-secondary" onClick={() => onNavigate('vault')}>
            Open Memory Vault
          </button>
          <button className="btn-ghost-sm" onClick={refreshStatus}>
            Refresh Status
          </button>
        </div>
      </div>
    </div>
  )
}
