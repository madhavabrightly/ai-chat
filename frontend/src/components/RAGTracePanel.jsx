export default function RAGTracePanel({ trace }) {
  if (!trace || !trace.retrieval_time_ms) return null

  return (
    <div className="rag-trace-panel">
      <div className="rag-trace-header">
        <span className="rag-trace-icon">🔬</span>
        <span className="rag-trace-title">How This Answer Was Generated</span>
      </div>
      <p className="rag-trace-note">
        This explains how Memory Twin AI generated the answer.
      </p>

      <div className="rag-trace-grid">
        <div className="rag-trace-row">
          <span className="rag-trace-lbl">Your Question</span>
          <span className="rag-trace-val">{trace.question}</span>
        </div>
        <div className="rag-trace-row">
          <span className="rag-trace-lbl">Embedding Model</span>
          <span className="rag-trace-val">{trace.embedding_model}</span>
        </div>
        <div className="rag-trace-row">
          <span className="rag-trace-lbl">Vector Database</span>
          <span className="rag-trace-val">{trace.vector_db}</span>
        </div>
        <div className="rag-trace-row">
          <span className="rag-trace-lbl">Top-K Retrieved</span>
          <span className="rag-trace-val">{trace.top_k}</span>
        </div>
        <div className="rag-trace-row">
          <span className="rag-trace-lbl">LLM Model</span>
          <span className="rag-trace-val">{trace.llm_model}</span>
        </div>
        <div className="rag-trace-row">
          <span className="rag-trace-lbl">ChromaDB Path</span>
          <span className="rag-trace-val" style={{ fontSize: '0.68rem' }}>{trace.chromadb_path}</span>
        </div>
        <div className="rag-trace-row">
          <span className="rag-trace-lbl">Retrieval Time</span>
          <span className="rag-trace-val">{trace.retrieval_time_ms}ms</span>
        </div>
        <div className="rag-trace-row">
          <span className="rag-trace-lbl">Generation Time</span>
          <span className="rag-trace-val">{trace.generation_time_ms}ms</span>
        </div>
        <div className="rag-trace-row rag-trace-total">
          <span className="rag-trace-lbl">Total Time</span>
          <span className="rag-trace-val">{trace.total_time_ms}ms</span>
        </div>
      </div>

      {trace.retrieved_memories && trace.retrieved_memories.length > 0 && (
        <div className="rag-trace-mems">
          <div className="rag-trace-mems-title">Retrieved Memories (by relevance)</div>
          {trace.retrieved_memories.map((m, i) => (
            <div key={i} className="rag-trace-mem-row">
              <span className="rag-trace-mem-num">{i + 1}</span>
              <span className="rag-trace-mem-name">{m.title}</span>
              <span className="rag-trace-mem-cat">{m.category}</span>
              <span className="rag-trace-mem-score">{(m.relevance_score * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
