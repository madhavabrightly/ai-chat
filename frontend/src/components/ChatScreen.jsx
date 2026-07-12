import { useState, useEffect, useRef, useCallback } from 'react'
import { useChat } from '../context/ChatContext.jsx'
import { importMemoryFile, sendChatMessageStream, saveMemory } from '../api/memoryApi.js'
import RAGTracePanel from './RAGTracePanel.jsx'
import detectMemoryIntent from '../utils/memoryDetector.js'
import detectAvatarMood from '../utils/avatarMood.js'
import { guardAnswer } from '../utils/languageGuard.js'
import {
  getTempImportMeta,
  getTempImportData,
  setTempImport,
  clearTempImport,
  hasTempImport,
} from '../utils/tempImportStore.js'

const SUGGESTIONS = [
  'What advice would you give me?',
  'Tell me about your childhood',
  'What made you proud?',
  'What do you believe about life?',
  'How was your first love?',
  'Tell me a funny story',
]

const LOADING_MESSAGES = [
  'Memory Twin is searching memories...',
  'Still thinking — the model is generating on AMD compute...',
  'This response is taking longer than usual. You can wait or retry.',
]

export default function ChatScreen({ onAvatarState, onAvatarMood, onLastAnswer, companion }) {
  const {
    messages,
    addMessage,
    updateMessage,
    clearMessages,
    lastTrace,
    setLastTrace,
    findMessageByRequestId,
  } = useChat()
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
  const activeAbortRef = useRef(new Map())

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    if (!loading) {
      setLoadingMsgIdx(0)
      if (loadingTimerRef.current) {
        clearInterval(loadingTimerRef.current)
        loadingTimerRef.current = null
      }
      return
    }
    loadingTimerRef.current = setInterval(
      () => setLoadingMsgIdx(prev => Math.min(prev + 1, LOADING_MESSAGES.length - 1)),
      15000
    )
    return () => {
      if (loadingTimerRef.current) {
        clearInterval(loadingTimerRef.current)
        loadingTimerRef.current = null
      }
    }
  }, [loading])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      activeAbortRef.current.forEach(controller => {
        try { controller.abort() } catch {}
      })
      activeAbortRef.current.clear()
    }
  }, [])

  // ---------------------------------------------------------------------------
  // Send message (with proper request state, retry payload, trace association)
  // ---------------------------------------------------------------------------

  const send = useCallback(function(q, retryPayload) {
    // If retryPayload is provided, use its question (not the cleared input field)
    const text = retryPayload?.question || q || input
    if (!text?.trim()) return
    setInput('')

    const abortController = new AbortController()

    // Build retry payload (used if user clicks Retry)
    const history = messages
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .slice(-20)
      .map(m => ({ role: m.role, content: m.content }))

    const tempCtx = hasTempImport() ? {
      enabled: true,
      file_name: importMeta?.file_name || '',
      session_id: importMeta?.session_id || '',
      summary: importMeta?.summary || '',
      style_profile: {
        tone: importMeta?.tone || 'warm',
        chat_style: 'Adapted from imported chat',
        emotions: importMeta?.emotions || [],
      },
      chunks: importChunks,
    } : null

    const requestPayload = retryPayload || {
      question: text,
      companionType: companion || 'female',
      history,
      tempContext: tempCtx,
    }

    // Add user message FIRST (before any async work)
    const userMsgId = addMessage('user', text)

    // Detect memory intent — save memory in parallel with chat request
    const memResult = detectMemoryIntent(text)
    if (memResult.shouldSave) {
      saveMemory({
        title: memResult.title,
        text: text,
        category: memResult.category || 'Personal',
        emotion: memResult.emotion || 'Neutral',
        tags: memResult.tags || [],
      }).then(res => {
        if (res.ok && res.memory_id) {
          addMessage('system', `💾 Memory saved: "${memResult.title}" (${res.memory_id})`)
        } else {
          addMessage('system', `⚠️ Memory was not saved. Retry.`)
        }
      }).catch(() => {
        addMessage('system', `⚠️ Memory was not saved. Retry.`)
      })
    }

    setLoading(true)
    onAvatarState && onAvatarState('thinking')

    // Add streaming placeholder message
    const streamingId = addMessage('assistant', '', {
      streaming: true,
      status: 'streaming',
    })

    activeAbortRef.current.set(streamingId, abortController)

    let fullAnswer = ''
    let traceData = null
    let retrievedMemories = []

    sendChatMessageStream({
      question: requestPayload.question,
      companionType: requestPayload.companionType,
      history: requestPayload.history,
      tempContext: requestPayload.tempCtx,
      signal: abortController.signal,
      onToken: (delta) => {
        if (activeAbortRef.current.get(streamingId) !== abortController) return
        fullAnswer += delta
        updateMessage(streamingId, { content: fullAnswer })
      },
      onTrace: (trace) => {
        if (activeAbortRef.current.get(streamingId) !== abortController) return
        traceData = trace
        if (trace.rag_trace) setLastTrace(trace.rag_trace)
      },
      onDone: (done) => {
        if (activeAbortRef.current.get(streamingId) !== abortController) return
        const finalAnswer = done.answer || fullAnswer
        retrievedMemories = done.retrieved_memories || []
        // Only mark memory_based if memories were actually retrieved
        const memoryBased = retrievedMemories.length > 0
        updateMessage(streamingId, {
          content: guardAnswer(finalAnswer),
          streaming: false,
          status: 'complete',
          memory_based: memoryBased,
          retrieved_memories: retrievedMemories,
          trace: traceData,
          request_id: done.request_id || null,
        })
        if (onLastAnswer) onLastAnswer(finalAnswer, text, retrievedMemories)
        const mood = detectAvatarMood(finalAnswer, retrievedMemories)
        if (onAvatarMood) onAvatarMood(mood)
        if (onAvatarState) onAvatarState('idle')
      },
      onError: (err) => {
        if (activeAbortRef.current.get(streamingId) !== abortController) return
        const errorMsg = err?.message || err || 'Stream error. Try again.'
        const errorCode = err?.code || 'STREAM_ERROR'
        updateMessage(streamingId, {
          content: `⚠️ ${errorMsg}`,
          streaming: false,
          status: 'error',
          isError: true,
          error_code: errorCode,
          // Store retry payload so user can retry with same context
          retry_payload: {
            question: requestPayload.question,
            companionType: requestPayload.companionType,
            history: requestPayload.history,
            tempContext: requestPayload.tempCtx,
          },
        })
        if (onLastAnswer) onLastAnswer('')
        if (onAvatarState) onAvatarState('idle')
        if (onAvatarMood) onAvatarMood('calm')
      },
    }).finally(() => {
      if (activeAbortRef.current.get(streamingId) === abortController) {
        activeAbortRef.current.delete(streamingId)
      }
      setLoading(activeAbortRef.current.size > 0)
    })
  }, [input, messages, onAvatarState, onAvatarMood, onLastAnswer, companion,
      addMessage, updateMessage, setLastTrace, importMeta, importChunks])

  // Retry a failed message using its stored retry_payload
  const retryMessage = useCallback((messageId) => {
    const msg = findMessageByRequestId(messageId) || messages.find(m => m.id === messageId)
    if (!msg || !msg.retry_payload) return
    // Clear the error state on the message
    updateMessage(messageId, {
      content: '',
      streaming: true,
      status: 'streaming',
      isError: false,
      error_code: null,
      retry_payload: null,
    })
    // Re-send with the stored payload
    send(null, msg.retry_payload)
  }, [findMessageByRequestId, messages, updateMessage, send])

  // ---------------------------------------------------------------------------
  // Import handling
  // ---------------------------------------------------------------------------

  async function handleImportFile(e) {
    const MAX_FILE_SIZE = 20 * 1024 * 1024  // 20MB

    const file = e.target.files?.[0]
    if (!file) return

    if (file.size > MAX_FILE_SIZE) {
      addMessage('system', `⚠️ File too large (${(file.size / 1024 / 1024).toFixed(1)}MB). Max 20MB.`)
      e.target.value = ''
      return
    }

    addMessage('system', `📥 Indexing "${file.name}" for memory retrieval...`)
    const result = await importMemoryFile(file)
    if (!result.ok) {
      addMessage('system', `⚠️ Could not import "${file.name}": ${result.message || 'backend import failed'}.`)
      e.target.value = ''
      return
    }

    const data = result.data || {}
    const meta = {
      session_id: data.session_id,
      file_name: data.file_name || file.name,
      summary: data.summary || `${data.message_count || 0} imported messages`,
      tone: data.tone || 'warm',
      emotions: data.emotions || [],
      message_count: data.message_count || 0,
    }
    const previewChunks = (data.messages || []).slice(0, 40)

    setTempImport(meta, previewChunks)
    setImportMeta(meta)
    setImportChunks(previewChunks)
    addMessage('system', `✅ Imported "${file.name}" — ${meta.message_count} messages indexed, tone: ${meta.tone}`)
    setShowImport(false)
    e.target.value = ''
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
            {loading ? (
              <span className="status-loading">
                <span className="status-dot" />
                {LOADING_MESSAGES[loadingMsgIdx]}
              </span>
            ) : companion ? (
              <span className="status-online">
                <span className="status-dot" />
                online · ready
              </span>
            ) : (
              <span className="status-idle">choose companion →</span>
            )}
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
                  <button key={s} className="chip-sug" onClick={() => send(s)}>{s}</button>
                ))}
              </div>
            )}
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id}>
            {msg.role === 'user' && (
              <div className="wa-msg wa-user">
                <div className="wa-bubble wa-bubble-user">{msg.content}<div className="wa-time">{msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}</div></div>
              </div>
            )}
            {msg.role === 'assistant' && (
              <div className="wa-msg wa-ai">
                <div className="wa-avatar-small">{companion === 'male' ? '👤' : '👩'}</div>
                <div className={`wa-bubble ${msg.isError ? 'wa-bubble-error' : 'wa-bubble-ai'}`}>
                  {msg.streaming && !msg.content ? (
                    <span className="wa-typing-dots"><span className="wa-dot" /><span className="wa-dot" /><span className="wa-dot" /></span>
                  ) : (
                    <>
                      {msg.content}
                      {msg.streaming && <span className="wa-cursor">▊</span>}
                    </>
                  )}
                  <div className="wa-time">
                    {msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                    {msg.memory_based && msg.retrieved_memories?.length > 0 && (
                      <span className="wa-badge">based on {msg.retrieved_memories.length} memor{msg.retrieved_memories.length === 1 ? 'y' : 'ies'}</span>
                    )}
                  </div>
                </div>
                {msg.isError && (
                  <button
                    className="btn-ghost-xs"
                    style={{ marginLeft: 34, marginTop: 4 }}
                    onClick={() => retryMessage(msg.id)}
                  >
                    🔁 Retry
                  </button>
                )}
              </div>
            )}
            {msg.role === 'system' && (
              <div className="wa-msg wa-system"><div className="wa-bubble wa-bubble-system">{msg.content}</div></div>
            )}
          </div>
        ))}

        <div ref={endRef} />
      </div>

      {lastTrace && <div className="rag-trace-wrapper"><RAGTracePanel trace={lastTrace} /></div>}

      <div className="chat-input-bar">
        <textarea
          ref={inputRef}
          className="wa-input"
          placeholder={companion ? "Type a message... (Enter to send, Shift+Enter for new line)" : "Choose a companion first →"}
          value={input}
          onChange={e => {
            setInput(e.target.value)
            // Auto-grow
            e.target.style.height = 'auto'
            e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
          }}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              if (input.trim() && companion) send()
            }
          }}
          disabled={!companion}
          rows={1}
        />
        {loading && (
          <button
            className="wa-stop"
            onClick={() => {
              activeAbortRef.current.forEach(controller => {
                try { controller.abort() } catch {}
              })
            }}
            title="Stop current replies"
            aria-label="Stop current replies"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="6" width="12" height="12" rx="2"/>
            </svg>
          </button>
        )}
        <button
          className="wa-send"
          onClick={() => send()}
          disabled={!input.trim() || !companion}
          title="Send message"
          aria-label="Send message"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/>
            <path d="m21.854 2.147-10.94 10.939"/>
          </svg>
        </button>
      </div>
    </div>
  )
}
