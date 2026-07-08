import { useState, useEffect, useRef } from 'react'
import { chatWithMemory, fetchComputeStatus } from '../api/memoryApi.js'
import GlowingOrb from './GlowingOrb.jsx'
import AMDComputeStatus from './AMDComputeStatus.jsx'
import MemoryRetrievedPanel from './MemoryRetrievedPanel.jsx'

const SUGGESTIONS = [
  'What advice would you give me?',
  'Tell me about your childhood',
  'What made you proud?',
  'What do you believe about life?',
]

export default function ChatScreen({ onNavigate, backendOnline: parentOnline, computeStatus: parentStatus, refreshStatus }) {
  const [question, setQuestion] = useState('')
  const [lastQ, setLastQ] = useState('')
  const [answer, setAnswer] = useState('')
  const [retrieved, setRetrieved] = useState([])
  const [compute, setCompute] = useState(parentStatus)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const endRef = useRef(null)

  useEffect(() => {
    if (parentStatus) setCompute(parentStatus)
    else fetchComputeStatus().then(setCompute).catch(() => {})
  }, [parentStatus])

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [answer, retrieved])

  function send(q) {
    const query = q || question
    if (!query.trim() || loading) return
    setLastQ(query)
    setQuestion('')
    setLoading(true)
    setError('')
    setAnswer('')
    setRetrieved([])
    chatWithMemory(query)
      .then(data => {
        setAnswer(data.answer)
        setRetrieved(data.retrieved_memories || [])
        if (data.compute_status) setCompute(data.compute_status)
      })
      .catch(() => setError('Backend offline or API error. No demo data is shown because mock mode is disabled.'))
      .finally(() => setLoading(false))
  }

  return (
    <div className="screen chat-s">
      <div className="chat-layout">
        <div className="chat-main">
          <div className="chat-head">
            <button className="btn-ghost-sm" onClick={() => onNavigate('home')}>Home</button>
            <button className="btn-ghost-sm" onClick={() => onNavigate('vault')}>Memory Vault</button>
          </div>

          <div className="chat-scroll">
            {!lastQ && !answer && !loading && (
              <div className="chat-welcome">
                <GlowingOrb pulsing={false} size={90} />
                <h2>Memory Twin AI</h2>
                <p className="chat-sub">Ask me anything about the memories I hold.</p>
                <div className="sug-row">
                  {SUGGESTIONS.map(s => (
                    <button key={s} className="chip-sug" onClick={() => send(s)} disabled={loading}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {loading && (
              <div className="loading-indicator">
                <GlowingOrb pulsing size={70} />
                <p className="loading-text">Searching memories...</p>
              </div>
            )}

            {error && <div className="err-banner">{error}</div>}

            {lastQ && !loading && (
              <div className="msg msg-user"><div className="msg-b user-b">{lastQ}</div></div>
            )}

            {answer && (
              <div className="msg msg-ai">
                <div className="msg-b ai-b"><p>{answer}</p></div>
              </div>
            )}

            {retrieved.length > 0 && !loading && (
              <div className="chat-retrieved-mobile">
                <MemoryRetrievedPanel memories={retrieved} />
              </div>
            )}

            <div ref={endRef} />
          </div>

          <div className="chat-input-area">
            <input
              className="ci"
              placeholder="Ask a question..."
              value={question}
              onChange={e => setQuestion(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !loading && send()}
              disabled={loading}
            />
            <button className="btn-send" onClick={() => send()} disabled={loading || !question.trim()}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/>
                <path d="m21.854 2.147-10.94 10.939"/>
              </svg>
            </button>
          </div>
        </div>

        <div className="chat-side">
          <AMDComputeStatus status={compute} backendOnline={parentOnline} onRefresh={refreshStatus} />
          <MemoryRetrievedPanel memories={retrieved} />
        </div>
      </div>
    </div>
  )
}
