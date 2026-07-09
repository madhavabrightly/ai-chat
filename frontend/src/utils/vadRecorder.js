/**
 * VAD-based audio recorder using @ricky0123/vad-web.
 * No MediaRecorder needed — VAD delivers Float32Array audio in onSpeechEnd.
 */
import { MicVAD } from '@ricky0123/vad-web'
let vadInstance = null
let cb = { start: null, end: null, error: null }
let active = false

function float32ToWav(bytes) {
  const len = bytes.length
  const buf = new ArrayBuffer(44 + len * 2)
  const dv = new DataView(buf)
  const sr = 16000
  const w = (off, v, sz) => { if (sz === 2) dv.setUint16(off, v, true); else dv.setUint32(off, v, true) }
  w(0, 0x46464952, 4); w(4, 36 + len * 2, 4); w(8, 0x45564157, 4)
  w(12, 0x20746d66, 4); w(16, 16, 4); w(20, 1, 2); w(22, 1, 2); w(24, sr, 4); w(28, sr * 2, 4); w(32, 2, 2); w(34, 16, 2)
  w(36, 0x61746164, 4); w(40, len * 2, 4)
  for (let i = 0; i < len; i++) {
    const s = Math.max(-1, Math.min(1, bytes[i]))
    dv.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true)
  }
  return new Blob([buf], { type: 'audio/wav' })
}

export async function startVadRecording({ onSpeechStart, onSpeechEnd, onError }) {
  if (active) return
  active = true
  cb = { start: onSpeechStart, end: onSpeechEnd, error: onError }

  try {
    vadInstance = await MicVAD.new({
      onSpeechStart: () => { console.log('[VAD] speech_start'); if (cb.start) cb.start() },
      onSpeechRealStart: () => {},
      onSpeechEnd: (audio) => {
        console.log('[VAD] speech_end samples=' + (audio ? audio.length : 0))
        if (audio && audio.length > 2000 && cb.end) cb.end(float32ToWav(audio))
      },
      onVADMisfire: () => {},
      onFrameProcessed: () => {},
      onError: (e) => { console.error('[VAD] error', e); if (cb.error) cb.error(e) },
      startOnLoad: true,
    })
    console.log('[VAD] started')
    return true
  } catch (e) {
    console.error('[VAD] init failed', e)
    active = false
    if (cb.error) cb.error(e)
    return false
  }
}

export function stopVadRecording() {
  active = false
  if (vadInstance) { try { vadInstance.destroy() } catch {}; vadInstance = null }
  console.log('[VAD] stopped')
}

export function pauseVad() {
  if (vadInstance) try { vadInstance.pause() } catch {}
  console.log('[VAD] paused')
}

export function resumeVad() {
  if (vadInstance) try { vadInstance.start() } catch {}
  console.log('[VAD] resumed')
}

export function isVadActive() { return active }
