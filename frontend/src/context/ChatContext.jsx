import { createContext, useContext, useState, useEffect, useCallback } from 'react'

const STORAGE_KEY = 'memoryTwin.chatMessages'

function loadMessages() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch {}
  return []
}

function saveMessages(msgs) {
  try {
    // Keep only last 100 messages for storage
    const toSave = msgs.slice(-100)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave))
  } catch {}
}

const ChatContext = createContext(null)

export function ChatProvider({ children }) {
  const [messages, setMessages] = useState(loadMessages)
  const [lastTrace, setLastTrace] = useState(null)

  // Persist to localStorage on change
  useEffect(() => {
    saveMessages(messages)
  }, [messages])

  const addMessage = useCallback((role, content, extra = {}) => {
    setMessages(prev => [...prev, { role, content, id: Date.now(), ...extra }])
  }, [])

  const clearMessages = useCallback(() => {
    setMessages([])
    setLastTrace(null)
    localStorage.removeItem(STORAGE_KEY)
  }, [])

  return (
    <ChatContext.Provider value={{ messages, addMessage, clearMessages, lastTrace, setLastTrace }}>
      {children}
    </ChatContext.Provider>
  )
}

export function useChat() {
  const ctx = useContext(ChatContext)
  if (!ctx) throw new Error('useChat must be used within ChatProvider')
  return ctx
}
