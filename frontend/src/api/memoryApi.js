const BASE = '' // same origin
const CHAT_TIMEOUT_MS = 95000

export async function healthCheck() {
  const r = await fetch(BASE + '/health')
  if (!r.ok) throw new Error('Backend offline')
  return r.json()
}

export async function fetchComputeStatus() {
  const r = await fetch(BASE + '/compute-status')
  if (!r.ok) throw new Error('Compute status unavailable')
  return r.json()
}

export async function fetchMemories() {
  const r = await fetch(BASE + '/memories')
  if (!r.ok) throw new Error('Memories unavailable')
  return r.json()
}

/**
 * Shared chat message function used by both ChatScreen and LiveCallScreen.
 */
export async function sendChatMessage({
  question,
  companionType = 'female',
  history = [],
  tempContext = null,
}) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS)

  const body = { question, history, companion_type: companionType }
  if (tempContext) {
    body.temporary_context = tempContext
  }

  try {
    const r = await fetch(BASE + '/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
    clearTimeout(timeout)

    if (!r.ok) {
      const text = await r.text().catch(() => '')
      return {
        ok: false,
        answer: `Backend returned status ${r.status}. Try again.`,
        error: `HTTP ${r.status}: ${text.slice(0, 100)}`,
        http_status: r.status,
      }
    }

    const data = await r.json()
    return {
      ok: true,
      answer: data.answer || '',
      retrieved_memories: data.retrieved_memories || [],
      rag_trace: data.rag_trace || {},
      avatar_action_plan: data.avatar_action_plan || {},
      exact_sources: data.exact_sources || [],
      emotion: data.emotion || {},
      realtime_engine: data.realtime_engine || {},
    }
  } catch (err) {
    clearTimeout(timeout)
    if (err.name === 'AbortError') {
      return { ok: false, answer: 'The model took too long. Try again.', error: 'timeout' }
    }
    return { ok: false, answer: 'Backend is not reachable. Check the server and API URL.', error: err.message }
  }
}

/** Legacy wrapper used by ChatScreen */
export async function chatWithMemory(question, history = [], companionType = 'female', tempContext = null) {
  const result = await sendChatMessage({ question, companionType, history, tempContext })
  if (!result.ok) throw new Error(result.error)
  return result
}

export async function saveMemory(memory) {
  const r = await fetch(BASE + '/memories', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(memory),
  })
  if (!r.ok) throw new Error('Save memory failed')
  return r.json()
}
