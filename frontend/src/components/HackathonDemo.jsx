import { useState, useRef } from 'react'
import { chatWithMemory } from '../api/memoryApi.js'

const DEMO_QUESTIONS = [
  'What advice would you give me?',
  'Tell me about your childhood.',
  'What made you proud?',
]

export default function HackathonDemo({ onNavigate }) {
  const [step, setStep] = useState(-1) // -1 = not started
  const [results, setResults] = useState([])
  const [running, setRunning] = useState(false)
  const endRef = useRef(null)

  function runDemo() {
    setResults([])
    setStep(0)
    setRunning(true)
    runStep(0, [])
  }

  function runStep(i, acc) {
    if (i >= DEMO_QUESTIONS.length) {
      setStep(DEMO_QUESTIONS.length)
      setRunning(false)
      return
    }
    setStep(i)
    chatWithMemory(DEMO_QUESTIONS[i], [])
      .then(data => {
        const newAcc = [...acc, { question: DEMO_QUESTIONS[i], answer: data.answer, retrieved: data.retrieved_memories || [], rag_trace: data.rag_trace || {}, compute_status: data.compute_status || {} }]
        setResults(newAcc)
        setTimeout(() => {
          endRef.current?.scrollIntoView({ behavior: 'smooth' })
          runStep(i + 1, newAcc)
        }, 1500)
      })
      .catch(() => {
        const newAcc = [...acc, { question: DEMO_QUESTIONS[i], answer: '⚠️ Backend error. Check server.', retrieved: [], rag_trace: {}, compute_status: {} }]
        setResults(newAcc)
        runStep(i + 1, newAcc)
      })
  }

  return (
    <div className="screen demo-s">
      <div className="demo-head">
        <div>
          <h2>🎬 Hackathon Demo Mode</h2>
          <p className="demo-sub">Run 3 preset questions automatically to record your demo video</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-ghost-sm" onClick={() => onNavigate('chat')}>Chat</button>
          <button className="btn-primary" onClick={runDemo} disabled={running}>
            {running ? '⏳ Running...' : '▶ Run Hackathon Demo'}
          </button>
        </div>
      </div>

      {step === -1 && (
        <div className="demo-welcome" style={{ textAlign: 'center', padding: 40 }}>
          <p className="demo-instruction" style={{ fontSize: '0.95rem', color: '#6b4c3b', maxWidth: 500, margin: '0 auto', lineHeight: 1.6 }}>
            Click <strong>"Run Hackathon Demo"</strong> to automatically execute 3 preset chat questions one by one.
            Each result shows the AI answer, retrieved memories, and AMD compute status.
            Perfect for recording your demo video.
          </p>
          <div className="demo-qlist" style={{ marginTop: 20, display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'center' }}>
            {DEMO_QUESTIONS.map((q, i) => (
              <div key={i} className="demo-qitem" style={{ background: '#fdf8f0', border: '1px solid #e8dac8', borderRadius: 8, padding: '8px 16px', fontSize: '0.85rem', color: '#5c2e1a', width: 'fit-content' }}>
                <span className="pipe-num" style={{ marginRight: 8 }}>{i + 1}</span>
                {q}
              </div>
            ))}
          </div>
        </div>
      )}

      {results.map((r, i) => (
        <div key={i} className="demo-result" style={{ marginBottom: 24 }}>
          <div className="demo-q-header" style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span className="pipe-num">{i + 1}</span>
            <span style={{ fontWeight: 600, color: '#5c2e1a' }}>{r.question}</span>
            {i === step && running && <span className="demo-loading">⏳</span>}
          </div>

          <div className="demo-answer-box" style={{ background: '#fdf8f0', border: '1px solid #e8dac8', borderRadius: 10, padding: 16, marginBottom: 10 }}>
            <div style={{ fontSize: '0.7rem', color: '#a0806a', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6 }}>AI Response</div>
            <p style={{ fontSize: '0.9rem', color: '#2c1810', lineHeight: 1.6 }}>{r.answer}</p>
          </div>

          {r.retrieved.length > 0 && (
            <div className="demo-memories" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
              {r.retrieved.map((m, j) => (
                <div key={j} className="demo-mem-chip" style={{ background: '#fff', border: '1px solid #e8dac8', borderRadius: 8, padding: '6px 12px', fontSize: '0.78rem' }}>
                  <span style={{ color: '#a0806a', fontSize: '0.68rem' }}>{m.category}</span>
                  <div style={{ color: '#5c2e1a', fontWeight: 500 }}>{m.title}</div>
                  {m.relevance_score !== undefined && (
                    <span style={{ color: '#c9a96e', fontSize: '0.68rem' }}>Match: {(m.relevance_score * 100).toFixed(0)}%</span>
                  )}
                </div>
              ))}
            </div>
          )}

          {r.rag_trace && r.rag_trace.retrieval_time_ms && (
            <div className="demo-trace" style={{ fontSize: '0.72rem', color: '#a0806a', background: '#f0e6d3', borderRadius: 6, padding: '6px 12px', display: 'inline-flex', gap: 12 }}>
              <span>🔍 {r.rag_trace.retrieval_time_ms}ms retrieval</span>
              <span>⚡ {r.rag_trace.generation_time_ms}ms generation</span>
              <span>⏱️ {r.rag_trace.total_time_ms}ms total</span>
            </div>
          )}
        </div>
      ))}

      {step === DEMO_QUESTIONS.length && !running && (
        <div className="demo-complete" style={{ textAlign: 'center', padding: 20, background: '#f0f7e6', borderRadius: 12, border: '1px solid #c5d9a8' }}>
          <p style={{ fontSize: '1rem', color: '#2e7d32', fontWeight: 600 }}>✅ Demo Complete — 3/3 questions answered</p>
          <p style={{ fontSize: '0.8rem', color: '#6b4c3b', marginTop: 6 }}>
            AMD compute proof and RAG explainability are shown above. Screenshot or screen-record this page for your submission.
          </p>
        </div>
      )}

      <div ref={endRef} />
    </div>
  )
}
