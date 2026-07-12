/**
 * Memory Twin AI — Frontend API client
 *
 * Provides a consistent requestJson helper, structured error codes, and
 * AbortSignal support for all backend calls.
 *
 * Error codes (returned in `error.code`):
 *   - NETWORK_ERROR       — fetch failed (offline, DNS, CORS)
 *   - TIMEOUT             — request exceeded timeout
 *   - CANCELLED           — caller aborted via AbortSignal
 *   - HTTP_ERROR          — non-2xx response with body
 *   - PARSE_ERROR         — response body not valid JSON
 *   - BACKEND_ERROR       — backend returned {ok: false} or {error: ...}
 *   - STREAM_TIMEOUT      — SSE stream exceeded timeout
 *   - STREAM_PARSE_ERROR  — SSE event payload not valid JSON
 *   - STREAM_ERROR        — backend sent {type: "error"} event
 */

const BASE = ''
const CHAT_TIMEOUT_MS = 50000
const ASR_TIMEOUT_MS = 45000
const HEALTH_TIMEOUT_MS = 5000

/**
 * Generate a unique request ID for tracing.
 */
function generateRequestId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `req_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

/**
 * Build a structured error object.
 */
function makeError(code, message, extra = {}) {
  return {
    ok: false,
    code,
    message,
    ...extra,
  }
}

/**
 * Consistent JSON request helper.
 *
 * @param {string} path - API path (e.g. "/chat")
 * @param {object} options
 * @param {string} options.method - HTTP method (default POST)
 * @param {object} options.body - JSON body
 * @param {object} options.headers - Additional headers
 * @param {number} options.timeoutMs - Timeout in ms (default CHAT_TIMEOUT_MS)
 * @param {AbortSignal} options.signal - External abort signal
 * @returns {Promise<{ok: boolean, data?: any, error?: object, request_id?: string}>}
 */
export async function requestJson(path, {
  method = 'POST',
  body = null,
  headers = {},
  timeoutMs = CHAT_TIMEOUT_MS,
  signal = null,
} = {}) {
  const requestId = generateRequestId()
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  // Chain external signal to internal controller
  if (signal) {
    if (signal.aborted) {
      controller.abort()
    } else {
      signal.addEventListener('abort', () => controller.abort(), { once: true })
    }
  }

  try {
    const fetchOptions = {
      method,
      headers: {
        'Content-Type': 'application/json',
        'X-Request-ID': requestId,
        ...headers,
      },
      signal: controller.signal,
    }
    if (body !== null && body !== undefined) {
      fetchOptions.body = JSON.stringify(body)
    }

    const r = await fetch(BASE + path, fetchOptions)
    clearTimeout(timeoutId)

    // Read response body once
    const text = await r.text().catch(() => '')
    let data = null
    if (text) {
      try {
        data = JSON.parse(text)
      } catch {
        // Non-JSON response — treat as HTTP error
        if (!r.ok) {
          return makeError('HTTP_ERROR', `HTTP ${r.status}: ${text.slice(0, 200)}`, {
            http_status: r.status,
            request_id: requestId,
          })
        }
        return makeError('PARSE_ERROR', 'Response was not valid JSON', {
          raw: text.slice(0, 200),
          request_id: requestId,
        })
      }
    }

    if (!r.ok) {
      return makeError(
        'HTTP_ERROR',
        data?.error || data?.detail || `HTTP ${r.status}`,
        {
          http_status: r.status,
          request_id: requestId,
          data,
        }
      )
    }

    return { ok: true, data, request_id: requestId }
  } catch (err) {
    clearTimeout(timeoutId)
    if (err.name === 'AbortError') {
      // Distinguish caller-cancelled from timeout
      if (signal && signal.aborted) {
        return makeError('CANCELLED', 'Request was cancelled', { request_id: requestId })
      }
      return makeError('TIMEOUT', `Request timed out after ${timeoutMs}ms`, { request_id: requestId })
    }
    return makeError('NETWORK_ERROR', err.message || 'Network error', { request_id: requestId })
  }
}

// ---------------------------------------------------------------------------
// Health & status
// ---------------------------------------------------------------------------

export async function healthCheck() {
  const r = await requestJson('/health', { method: 'GET', timeoutMs: HEALTH_TIMEOUT_MS })
  if (!r.ok) throw new Error(r.message || 'Backend offline')
  return r.data
}

export async function fetchComputeStatus() {
  const r = await requestJson('/compute-status', { method: 'GET', timeoutMs: HEALTH_TIMEOUT_MS })
  if (!r.ok) throw new Error(r.message || 'Compute status unavailable')
  return r.data
}

export async function fetchMemories() {
  const r = await requestJson('/memories', { method: 'GET', timeoutMs: HEALTH_TIMEOUT_MS })
  if (!r.ok) throw new Error(r.message || 'Memories unavailable')
  return r.data
}

// ---------------------------------------------------------------------------
// Chat — non-streaming
// ---------------------------------------------------------------------------

/**
 * Send a chat message and receive a complete response.
 * Returns a normalized result with ok flag and structured error.
 */
export async function sendChatMessage({
  question,
  companionType = 'female',
  history = [],
  tempContext = null,
  voiceMode = false,
  signal = null,
} = {}) {
  const body = { question, history, companion_type: companionType, voice_mode: voiceMode }
  if (tempContext) {
    body.temporary_context = tempContext
  }

  const r = await requestJson('/chat', {
    method: 'POST',
    body,
    timeoutMs: CHAT_TIMEOUT_MS,
    signal,
  })

  if (!r.ok) {
    return {
      ok: false,
      answer: friendlyErrorMessage(r),
      error: r.message,
      code: r.code,
      http_status: r.http_status,
      request_id: r.request_id,
    }
  }

  const data = r.data || {}
  return {
    ok: true,
    answer: data.answer || '',
    retrieved_memories: data.retrieved_memories || [],
    rag_trace: data.rag_trace || {},
    avatar_action_plan: data.avatar_action_plan || {},
    exact_sources: data.exact_sources || [],
    emotion: data.emotion || {},
    realtime_engine: data.realtime_engine || {},
    request_id: r.request_id,
  }
}

export async function importMemoryFile(file, { signal = null } = {}) {
  const requestId = generateRequestId()
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS)

  if (signal) {
    if (signal.aborted) {
      controller.abort()
    } else {
      signal.addEventListener('abort', () => controller.abort(), { once: true })
    }
  }

  const form = new FormData()
  form.append('file', file)

  try {
    const r = await fetch(BASE + '/memory/import/preview', {
      method: 'POST',
      headers: { 'X-Request-ID': requestId },
      body: form,
      signal: controller.signal,
    })
    clearTimeout(timeoutId)
    const data = await r.json().catch(() => null)
    if (!r.ok || data?.error) {
      return makeError('HTTP_ERROR', data?.error || `HTTP ${r.status}`, {
        http_status: r.status,
        request_id: requestId,
      })
    }
    return { ok: true, data, request_id: requestId }
  } catch (err) {
    clearTimeout(timeoutId)
    if (err.name === 'AbortError') {
      if (signal && signal.aborted) return makeError('CANCELLED', 'Import was cancelled', { request_id: requestId })
      return makeError('TIMEOUT', `Import timed out after ${CHAT_TIMEOUT_MS}ms`, { request_id: requestId })
    }
    return makeError('NETWORK_ERROR', err.message || 'Import failed', { request_id: requestId })
  }
}

export async function requestAvatarAction({
  answer,
  retrievedMemories = [],
  companionType = 'female',
} = {}) {
  const result = await requestJson('/avatar/action', {
    method: 'POST',
    body: {
      answer: String(answer || '').slice(0, 1200),
      retrieved_memories: retrievedMemories.slice(0, 3),
      companion_type: companionType,
    },
    timeoutMs: 3500,
  })

  if (!result.ok) return result
  return {
    ok: true,
    plan: result.data?.plan || {},
    request_id: result.request_id,
  }
}

// ---------------------------------------------------------------------------
// Chat — streaming (SSE)
// ---------------------------------------------------------------------------

/**
 * Streaming chat via Server-Sent Events.
 *
 * @param {object} options
 * @param {string} options.question
 * @param {string} options.companionType
 * @param {Array} options.history
 * @param {object|null} options.tempContext
 * @param {function} options.onToken - called with each token delta
 * @param {function} options.onTrace - called once with RAG trace
 * @param {function} options.onDone - called with final payload
 * @param {function} options.onAvatarAction - called with avatar action plan payloads
 * @param {function} options.onError - called with structured error
 * @param {AbortSignal} options.signal - external abort signal
 * @returns {Promise<{ok: boolean, request_id?: string, error?: object}>}
 */
export async function sendChatMessageStream({
  question,
  companionType = 'female',
  history = [],
  tempContext = null,
  voiceMode = false,
  onToken,
  onTrace,
  onDone,
  onAvatarAction,
  onError,
  signal = null,
} = {}) {
  const requestId = generateRequestId()
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS)

  if (signal) {
    if (signal.aborted) {
      controller.abort()
    } else {
      signal.addEventListener('abort', () => controller.abort(), { once: true })
    }
  }

  const body = { question, history, companion_type: companionType, voice_mode: voiceMode }
  if (tempContext) {
    body.temporary_context = tempContext
  }

  try {
    const r = await fetch(BASE + '/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Request-ID': requestId,
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
    clearTimeout(timeoutId)

    if (!r.ok) {
      const text = await r.text().catch(() => '')
      if (onError) {
        onError({
          code: 'HTTP_ERROR',
          message: `HTTP ${r.status}: ${text.slice(0, 200)}`,
          http_status: r.status,
          request_id: requestId,
        })
      }
      return { ok: false, request_id: requestId, code: 'HTTP_ERROR' }
    }

    const reader = r.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const payload = line.slice(6).trim()
        if (payload === '[DONE]') continue
        try {
          const event = JSON.parse(payload)
          // New event types (optimized streaming)
          if (event.type === 'chat.accepted') {
            // Request accepted — no UI action needed
            continue
          } else if (event.type === 'retrieval.started') {
            // Retrieval started — could show a spinner
            continue
          } else if (event.type === 'retrieval.completed') {
            // Build a rag_trace-like payload for onTrace
            if (onTrace) {
              onTrace({
                type: 'rag_trace',
                request_id: requestId,
                retrieved_memories: [],
                memory_count: event.memory_count || event.count || 0,
                retrieval_ms: event.retrieval_ms || event.ms || 0,
                reranker_used: event.reranker_used || false,
                rerank_ms: event.rerank_ms || 0,
              })
            }
            continue
          } else if (event.type === 'answer.first_token') {
            // First token arrived — could update UI
            continue
          } else if (event.type === 'answer.delta' && onToken) {
            onToken(event.delta || '')
          } else if (event.type === 'answer.completed' && onDone) {
            onDone({
              type: 'done',
              request_id: requestId,
              answer: event.answer || '',
              truth_level: event.truth_level || 'UNKNOWN',
              total_ms: event.total_ms || 0,
              retrieved_memories: event.retrieved_memories || [],
              avatar_action_plan: event.avatar_action_plan || {},
            })
          } else if (event.type === 'avatar.action') {
            if (onAvatarAction) onAvatarAction(event.plan || event.avatar_action_plan || event)
            continue
          } else if (event.type === 'tts.queued') {
            // TTS queued — non-blocking
            continue
          } else if (event.type === 'chat.error') {
            if (onError) {
              onError({
                code: 'STREAM_ERROR',
                message: event.message || 'stream error',
                request_id: requestId,
              })
            }
            return { ok: false, request_id: requestId, code: 'STREAM_ERROR' }
          }
          // Legacy event types (backward compat)
          else if (event.type === 'rag_trace' && onTrace) {
            onTrace({ ...event, request_id: requestId })
          } else if (event.type === 'token' && onToken) {
            onToken(event.delta || '')
          } else if (event.type === 'done' && onDone) {
            onDone({ ...event, request_id: requestId })
          } else if (event.type === 'error') {
            if (onError) {
              onError({
                code: 'STREAM_ERROR',
                message: event.message || 'stream error',
                request_id: requestId,
              })
            }
            return { ok: false, request_id: requestId, code: 'STREAM_ERROR' }
          }
        } catch {
          if (onError) {
            onError({
              code: 'STREAM_PARSE_ERROR',
              message: 'Failed to parse stream event',
              request_id: requestId,
            })
          }
        }
      }
    }

    return { ok: true, request_id: requestId }
  } catch (err) {
    clearTimeout(timeoutId)
    if (err.name === 'AbortError') {
      if (signal && signal.aborted) {
        if (onError) onError({ code: 'CANCELLED', message: 'Stream cancelled', request_id: requestId })
        return { ok: false, request_id: requestId, code: 'CANCELLED' }
      }
      if (onError) onError({ code: 'STREAM_TIMEOUT', message: 'Stream timed out', request_id: requestId })
      return { ok: false, request_id: requestId, code: 'STREAM_TIMEOUT' }
    }
    if (onError) onError({ code: 'NETWORK_ERROR', message: err.message, request_id: requestId })
    return { ok: false, request_id: requestId, code: 'NETWORK_ERROR' }
  }
}

// ---------------------------------------------------------------------------
// Memory save
// ---------------------------------------------------------------------------

/**
 * Save a memory to the backend.
 * Returns {ok, memory, indexed} on success or {ok: false, error} on failure.
 */
export async function saveMemory(memory) {
  const r = await requestJson('/memories', {
    method: 'POST',
    body: memory,
    timeoutMs: CHAT_TIMEOUT_MS,
  })
  if (!r.ok) {
    return {
      ok: false,
      error: r.message || 'Save memory failed',
      code: r.code,
      request_id: r.request_id,
    }
  }
  return {
    ok: true,
    memory: r.data?.memory,
    indexed: r.data?.indexed ?? false,
    request_id: r.request_id,
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function friendlyErrorMessage(r) {
  switch (r.code) {
    case 'TIMEOUT':
    case 'STREAM_TIMEOUT':
      return 'The model took too long. Try again.'
    case 'CANCELLED':
      return 'Request was cancelled.'
    case 'NETWORK_ERROR':
      return 'Backend is not reachable. Check the server and API URL.'
    case 'HTTP_ERROR':
      return `Backend returned status ${r.http_status || 'error'}. Try again.`
    default:
      return 'Something went wrong. Try again.'
  }
}

/** Legacy wrapper used by HackathonDemo */
export async function chatWithMemory(question, history = [], companionType = 'female', tempContext = null) {
  const result = await sendChatMessage({ question, companionType, history, tempContext })
  if (!result.ok) throw new Error(result.error)
  return result
}
