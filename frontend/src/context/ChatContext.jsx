import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'

const STORAGE_KEY = 'memoryTwin.chatMessages'
const MAX_STORED_MESSAGES = 100
const MAX_IN_MEMORY_MESSAGES = 500

/**
 * Generate a stable unique ID using crypto.randomUUID() with fallback.
 * crypto.randomUUID() is available in all modern browsers and Node 19+.
 */
function generateId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  // Fallback: timestamp + random suffix (still collision-resistant for our scale)
  return `id_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`
}

/**
 * Validate and normalize a message object. Ensures all required fields exist
 * with correct types. Strips unknown fields to keep storage clean.
 */
function normalizeMessage(msg) {
  if (!msg || typeof msg !== 'object') return null
  const role = msg.role
  if (role !== 'user' && role !== 'assistant' && role !== 'system') return null
  return {
    id: typeof msg.id === 'string' ? msg.id : generateId(),
    role,
    content: typeof msg.content === 'string' ? msg.content : '',
    turn_id: typeof msg.turn_id === 'string' ? msg.turn_id : null,
    request_id: typeof msg.request_id === 'string' ? msg.request_id : null,
    status: ['pending', 'streaming', 'complete', 'error', 'cancelled'].includes(msg.status)
      ? msg.status
      : 'complete',
    streaming: Boolean(msg.streaming),
    isError: Boolean(msg.isError),
    memory_based: Boolean(msg.memory_based),
    retry_payload: msg.retry_payload && typeof msg.retry_payload === 'object'
      ? msg.retry_payload
      : null,
    created_at: typeof msg.created_at === 'number' ? msg.created_at : Date.now(),
  }
}

function loadMessages() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.map(normalizeMessage).filter(Boolean)
  } catch {
    return []
  }
}

function saveMessages(msgs) {
  try {
    const toSave = msgs.slice(-MAX_STORED_MESSAGES)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave))
  } catch {}
}

const ChatContext = createContext(null)

export function ChatProvider({ children }) {
  const [messages, setMessages] = useState(loadMessages)
  const [lastTrace, setLastTrace] = useState(null)
  const messagesRef = useRef(messages)

  // Keep ref in sync for use inside callbacks that may close over stale state
  useEffect(() => {
    messagesRef.current = messages
  }, [messages])

  // Persist to localStorage on change
  useEffect(() => {
    saveMessages(messages)
  }, [messages])

  const addMessage = useCallback((role, content, extra = {}) => {
    const msg = normalizeMessage({
      role,
      content,
      id: extra.id || generateId(),
      turn_id: extra.turn_id || null,
      request_id: extra.request_id || null,
      status: extra.status || 'complete',
      streaming: extra.streaming || false,
      isError: extra.isError || false,
      memory_based: extra.memory_based || false,
      retry_payload: extra.retry_payload || null,
      created_at: Date.now(),
      ...extra,
    })
    if (!msg) return null
    setMessages(prev => {
      const next = [...prev, msg]
      // Bound in-memory count to prevent unbounded growth
      return next.length > MAX_IN_MEMORY_MESSAGES
        ? next.slice(-MAX_IN_MEMORY_MESSAGES)
        : next
    })
    return msg.id
  }, [])

  const updateMessage = useCallback((id, updates) => {
    if (!id) return
    setMessages(prev => prev.map(m => {
      if (m.id !== id) return m
      const merged = normalizeMessage({ ...m, ...updates, id: m.id })
      return merged || m
    }))
  }, [])

  const removeMessage = useCallback((id) => {
    if (!id) return
    setMessages(prev => prev.filter(m => m.id !== id))
  }, [])

  const findMessageByRequestId = useCallback((requestId) => {
    if (!requestId) return null
    return messagesRef.current.find(m => m.request_id === requestId) || null
  }, [])

  const clearMessages = useCallback(() => {
    setMessages([])
    setLastTrace(null)
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {}
  }, [])

  return (
    <ChatContext.Provider value={{
      messages,
      addMessage,
      updateMessage,
      removeMessage,
      findMessageByRequestId,
      clearMessages,
      lastTrace,
      setLastTrace,
    }}>
      {children}
    </ChatContext.Provider>
  )
}

export function useChat() {
  const ctx = useContext(ChatContext)
  if (!ctx) throw new Error('useChat must be used within ChatProvider')
  return ctx
}

export { generateId, normalizeMessage }
