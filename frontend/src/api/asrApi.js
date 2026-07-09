const BASE = ''
const ASR_TIMEOUT_MS = 45000

export async function transcribeAudio(audioBlob) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), ASR_TIMEOUT_MS)

  const fd = new FormData()
  fd.append('file', audioBlob, 'recording.wav')

  try {
    const r = await fetch(BASE + '/asr/transcribe', {
      method: 'POST',
      body: fd,
      signal: controller.signal,
    })
    clearTimeout(timeout)
    const data = await r.json()
    if (data.ok) {
      return { ok: true, transcript: data.transcript || '' }
    }
    return { ok: false, transcript: '', error: data.error || 'ASR failed' }
  } catch (err) {
    clearTimeout(timeout)
    if (err.name === 'AbortError') {
      return { ok: false, transcript: '', error: 'ASR request timed out' }
    }
    return { ok: false, transcript: '', error: err.message }
  }
}
