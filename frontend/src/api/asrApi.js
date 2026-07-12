/**
 * ASR (Automatic Speech Recognition) API client.
 *
 * Error codes:
 *   - NETWORK_ERROR — fetch failed
 *   - TIMEOUT       — request exceeded ASR_TIMEOUT_MS
 *   - CANCELLED     — caller aborted
 *   - HTTP_ERROR    — non-2xx response
 *   - ASR_FAILED    — backend returned {ok: false}
 *   - EMPTY_AUDIO   — audio blob too small
 */

import { apiBaseCandidates, apiUrl, shouldRetryApiStatus } from './baseUrl.js'

const ASR_TIMEOUT_MS = 45000
const MIN_AUDIO_BYTES = 100

function generateRequestId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `asr_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

/**
 * Transcribe an audio blob using the backend ASR endpoint.
 *
 * @param {Blob} audioBlob - Audio data (WAV preferred)
 * @param {object} options
 * @param {AbortSignal} options.signal - External abort signal
 * @returns {Promise<{ok: boolean, transcript?: string, error?: string, code?: string, request_id?: string}>}
 */
export async function transcribeAudio(audioBlob, { signal = null } = {}) {
  if (!audioBlob || audioBlob.size < MIN_AUDIO_BYTES) {
    return {
      ok: false,
      transcript: '',
      error: 'Audio too short',
      code: 'EMPTY_AUDIO',
    }
  }

  const requestId = generateRequestId()
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), ASR_TIMEOUT_MS)

  if (signal) {
    if (signal.aborted) {
      controller.abort()
    } else {
      signal.addEventListener('abort', () => controller.abort(), { once: true })
    }
  }

  const fd = new FormData()
  fd.append('file', audioBlob, 'recording.wav')

  try {
    let r = null
    let data = null
    const bases = apiBaseCandidates()
    for (let i = 0; i < bases.length; i += 1) {
      r = await fetch(apiUrl('/asr/transcribe', bases[i]), {
        method: 'POST',
        body: fd,
        signal: controller.signal,
        headers: {
          'X-Request-ID': requestId,
        },
      })
      data = await r.json().catch(() => ({}))
      if (r.ok || !shouldRetryApiStatus(r.status) || i === bases.length - 1) break
    }
    clearTimeout(timeoutId)

    if (!r.ok) {
      return {
        ok: false,
        transcript: '',
        error: data?.error || `HTTP ${r.status}`,
        code: 'HTTP_ERROR',
        http_status: r.status,
        request_id: requestId,
      }
    }

    if (data.ok) {
      return {
        ok: true,
        transcript: data.transcript || '',
        asr_model: data.asr_model,
        request_id: requestId,
      }
    }

    return {
      ok: false,
      transcript: '',
      error: data.error || 'ASR failed',
      code: 'ASR_FAILED',
      fallback: data.fallback,
      request_id: requestId,
    }
  } catch (err) {
    clearTimeout(timeoutId)
    if (err.name === 'AbortError') {
      if (signal && signal.aborted) {
        return { ok: false, transcript: '', error: 'Cancelled', code: 'CANCELLED', request_id: requestId }
      }
      return { ok: false, transcript: '', error: 'ASR request timed out', code: 'TIMEOUT', request_id: requestId }
    }
    return { ok: false, transcript: '', error: err.message, code: 'NETWORK_ERROR', request_id: requestId }
  }
}
