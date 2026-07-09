import { useState, useEffect, useRef, useCallback } from 'react'
import { useChat } from '../context/ChatContext.jsx'
import { sendChatMessage } from '../api/memoryApi.js'
import RAGTracePanel from './RAGTracePanel.jsx'
import detectMemoryIntent from '../utils/memoryDetector.js'
import detectAvatarMood from '../utils/avatarMood.js'
import { guardAnswer } from '../utils/languageGuard.js'
import { parseImportFile } from '../utils/importParser.js'
import { getTempImportMeta, getTempImportData, setTempImport, clearTempImport, hasTempImport } from '../utils/tempImportStore.js'

const SUGGESTIONS = [
  'What advice would you give me?',
  'Tell me about your childhood',
  'What made you proud?',
  'What do you believe about life?',
  "How was your first love?",
  "Tell me a funny story",
]

const LOADING_MESSAGES = [
  'Memory Twin is searching memories...',
  'Still thinking — the model is generating on AMD compute...',
  'This response is taking longer than usual. You can wait or retry.',
]

export default function ChatScreen({ onAvatarState, onAvatarMood, onLastAnswer, companion }) {
  const { messages, addMessage, clearMessages, lastTrace, setLastTrace } = useChat()
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingMsgIdx, setLoadingMsgIdx] = useState(0)
  const [importMeta, setImportMeta] = useState(getTempImportMeta)
  const [importChunks, setImportChunks] = useState(getTempImportData)
  const [showImport, setShowImport] = useState(false)
  const endRef = useRef(null)
  const inputRef = useRef(null)
  const loadingTimerRef = useRef(null)
  const fileRef = useRef(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, loading])

  useEffect(() => { inputRef.current?.focus() }, [])

  useEffect(() => {
    if (!loading) {
      setLoadingMsgIdx(0)
      if (loadingTimerRef.current) { clearInterval(loadingTimerRef.current); loadingTimerRef.current = null }
      return
    }
    loadingTimerRef.current = setInterval(() => setLoadingMsgIdx(prev => Math.min(prev + 1, LOADING_MESSAGES.length - 1)), 15000)
    return () => { if (loadingTimerRef.current) { clearInterval(loadingTimerRef.current); loadingTimerRef.current = null } }
  }, [loading])

  const send = useCallback(function(q) {
    const query = q || input
    if (!query.trim() || loading) return
    const text = query.trim()
    setInput('')

    const memResult = detectMemoryIntent(text)
    if (memResult.shouldSave) addMessage('system', `💾 Memory saved: "${memResult.title}"`)

    addMessage('user', text)
    setLoading(true)
    onAvatarState && onAvatarState('thinking')

    const history = messages.filter(m => m.role === 'user' || m.role === 'assistant').slice(-20).map(m => ({ role: m.role, content: m.content }))

    // Build temporary context from import
    const tempCtx = hasTempImport() ? {
      enabled: true,
      file_name: importMeta?.file_name || '',
      summary: importMeta?.summary || '',
      style_profile: { tone: importMeta?.tone || 'warm', chat_style: 'Adapted from imported chat', emotions: importMeta?.emotions || [] },
      chunks: importChunks,
    } : null

    sendChatMessage({ question: text, companionType: companion || 'female', history, tempContext: tempCtx })
      .then(data => {
        if (!data.ok) {
          addMessage('assistant', data.answer || 'Backend error. Try again.', { isError: true })
          onLastAnswer && onLastAnswer('')
          onAvatarState && onAvatarState('idle')
          onAvatarMood && onAvatarMood('calm')
          return
        }
        addMessage('assistant', guardAnswer(data.answer), { memory_based: true })
        if (data.rag_trace) setLastTrace(data.rag_trace)
        if (onLastAnswer) onLastAnswer(data.answer, text, data.retrieved_memories || [])

        if (data.exact_sources && data.exact_sources.length > 0) {
          setTimeout(() => addMessage('system', `📝 Exact memory found (${data.exact_sources.length} source(s))`), 200)
        }

        const mood = detectAvatarMood(data.answer, data.retrieved_memories || [])
        if (onAvatarMood) onAvatarMood(mood)
      })
      .finally(() => setLoading(false))
  }, [input, loading, messages, onAvatarState, onAvatarMood, onLastAnswer, companion, addMessage, setLastTrace, importMeta, importChunks])

  async function handleImportFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const raw = await file.text()
    const result = parseImportFile(raw, file.name)
    setTempImport({ file_name: result.file_name, summary: result.summary, tone: result.tone, emotions: result.emotions }, result.chunks)
    setImportMeta({ file_name: result.file_name, summary: result.summary, tone: result.tone, emotions: result.emotions })
    setImportChunks(result.chunks)
    addMessage('system', `📥 Imported "${file.name}" — ${result.chunks.length} chunks, tone: ${result.tone}`)
    setShowImport(false)
  }

  function handleClearImport() {
    clearTempImport()
    setImportMeta(null)
    setImportChunks([])
    addMessage('system', '🗑️ Temporary import cleared.')
  }

  return (
    <div className="chat-screen">
      <div className="chat-header">
        <div className="chat-header-avatar">
          <span className="chat-avatar-inner">{companion === 'male' ? '👤' : '👩'}</span>
        </div>
        <div className="chat-header-info">
          <div className="chat-header-name">Memory Twin</div>
          <div className="chat-header-status">
            {loading ? LOADING_MESSAGES[loadingMsgIdx] : companion ? 'online' : 'choose companion'}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 4 }}>
          {companion && (
            <button className="btn-ghost-xs" onClick={() => fileRef.current?.click()} title="Import chat or memory">
              📥
            </button>
          )}
          {messages.length > 0 && (
            <button className="btn-ghost-xs" onClick={clearMessages} title="Clear chat">🗑️</button>
          )}
        </div>
        <input ref={fileRef} type="file" accept=".txt,.json" hidden onChange={handleImportFile} />
      </div>

      <div className="chat-body">
        {messages.length === 0 && !loading && (
          <div className="chat-empty">
            <div className="chat-empty-icon">💬</div>
            <div className="chat-empty-text">
              {companion ? 'Say hello! I have memories to share with you.' : 'Choose a companion first on the right panel, then start chatting!'}
            </div>
            {companion && (
              <div className="sug-row" style={{ marginTop: 12 }}>
                {SUGGESTIONS.map(s => (
                  <button key={s} className="chip-sug" onClick={() => send(s)} disabled={loading}>{s}</button>
                ))}
              </div>
            )}
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id}>
            {msg.role === 'user' && (
              <div className="wa-msg wa-user">
                <div className="wa-bubble wa-bubble-user">{msg.content}<div className="wa-time">now</div></div>
              </div>
            )}
            {msg.role === 'assistant' && (
              <div className="wa-msg wa-ai">
                <div className="wa-avatar-small">{companion === 'male' ? '👤' : '👩'}</div>
                <div className={`wa-bubble ${msg.isError ? 'wa-bubble-error' : 'wa-bubble-ai'}`}>
                  {msg.content}
                  <div className="wa-time">now{msg.memory_based && <span className="wa-badge">based on memories</span>}</div>
                </div>
                {msg.isError && <button className="btn-ghost-xs" style={{ marginLeft: 34, marginTop: 4 }} onClick={() => send()}>🔁 Retry</button>}
              </div>
            )}
            {msg.role === 'system' && (
              <div className="wa-msg wa-system"><div className="wa-bubble wa-bubble-system">{msg.content}</div></div>
            )}
          </div>
        ))}

        {loading && (
          <div className="wa-msg wa-ai">
            <div className="wa-avatar-small">{companion === 'male' ? '👤' : '👩'}</div>
            <div className="wa-bubble wa-bubble-ai">
              <span className="wa-typing-dots"><span className="wa-dot" /><span className="wa-dot" /><span className="wa-dot" /></span>
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      {lastTrace && <div className="rag-trace-wrapper"><RAGTracePanel trace={lastTrace} /></div>}

      <div className="chat-input-bar">
        <input ref={inputRef} className="wa-input" placeholder="Type a message..." value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          disabled={loading || !companion} />
        <button className="wa-send" onClick={() => send()} disabled={loading || !input.trim() || !companion}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/>
            <path d="m21.854 2.147-10.94 10.939"/>
          </svg>
        </button>
      </div>
    </div>
  )
}
