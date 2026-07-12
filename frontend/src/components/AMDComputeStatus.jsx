export default function AMDComputeStatus({ status, backendOnline, onRefresh }) {
  if (!status) {
    return (
      <div className="panel amd-panel">
        <div className="panel-h">
          <h3>AMD Compute</h3>
          <button className="btn-ghost-xs" onClick={onRefresh}>Refresh</button>
        </div>
        <p className="panel-na">Compute status unavailable.</p>
      </div>
    )
  }

  const modelCachePath = status.model_cache_path || status.model_root || 'Unavailable'

  const rows = [
    ['Device', status.device],
    ['Torch', status.torch_version],
    ['GPU', status.cuda_available ? 'Available' : 'N/A'],
    ['ROCm/CUDA', status.cuda_or_rocm_version || (status.cuda_available ? 'ROCm (AMD)' : 'N/A')],
    ['LLM', status.llm_model],
    ['Embed', status.embedding_model],
    ['Cache', modelCachePath],
    ['ChromaDB', status.chromadb_path],
    ['Task', status.task],
  ]

  return (
    <div className="panel amd-panel">
      <div className="panel-h">
        <h3>AMD Compute</h3>
        <div className="panel-h-right">
          <span className={`sb-badge ${backendOnline ? 'sb-live' : 'sb-off'}`}>
            <span className="sb-dot" />{backendOnline ? 'Live' : 'Offline'}
          </span>
          <button className="btn-ghost-xs" onClick={onRefresh}>Refresh</button>
        </div>
      </div>
      <div className="panel-grid">
        {rows.map(([l, v]) => (
          <div key={l} className="panel-row">
            <span className="panel-lbl">{l}</span>
            <span className="panel-val">{typeof v === 'string' ? v : JSON.stringify(v)}</span>
          </div>
        ))}
      </div>
      {status.note && <p className="panel-note">{status.note}</p>}
    </div>
  )
}
