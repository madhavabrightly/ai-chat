/**
 * VAD-based audio recorder using @ricky0123/vad-web.
 *
 * State machine:
 *   idle → initializing → listening → speech_detected → listening → ... → stopping → idle
 *   any state → error → idle
 *
 * Key improvements:
 *   - Explicit state machine with valid transitions
 *   - Session token prevents stale callbacks from firing after stop
 *   - Audio validation (minimum samples, non-silent check)
 *   - Reactive state subscription via subscribeVadState()
 *   - Proper cleanup on stop (no leaked instances)
 */

import { MicVAD } from '@ricky0123/vad-web'

// VAD states
export const VAD_STATE = Object.freeze({
  IDLE: 'idle',
  INITIALIZING: 'initializing',
  LISTENING: 'listening',
  SPEECH_DETECTED: 'speech_detected',
  PAUSED: 'paused',
  STOPPING: 'stopping',
  ERROR: 'error',
})

// Valid state transitions
const VALID_TRANSITIONS = {
  [VAD_STATE.IDLE]: [VAD_STATE.INITIALIZING],
  [VAD_STATE.INITIALIZING]: [VAD_STATE.LISTENING, VAD_STATE.STOPPING, VAD_STATE.ERROR, VAD_STATE.IDLE],
  [VAD_STATE.LISTENING]: [VAD_STATE.SPEECH_DETECTED, VAD_STATE.PAUSED, VAD_STATE.STOPPING, VAD_STATE.ERROR],
  [VAD_STATE.SPEECH_DETECTED]: [VAD_STATE.LISTENING, VAD_STATE.STOPPING, VAD_STATE.ERROR],
  [VAD_STATE.PAUSED]: [VAD_STATE.LISTENING, VAD_STATE.STOPPING, VAD_STATE.ERROR],
  [VAD_STATE.STOPPING]: [VAD_STATE.IDLE, VAD_STATE.ERROR],
  [VAD_STATE.ERROR]: [VAD_STATE.IDLE, VAD_STATE.INITIALIZING],
}

// Module state
let vadInstance = null
let currentSession = null // { token, callbacks, state, lastSpeechStart }
let stateSubscribers = new Set()
let sessionCounter = 0

// Audio validation thresholds
const MIN_SAMPLES = 8000 // ~0.5s @ 16kHz
const MIN_RMS_THRESHOLD = 0.005 // Below this is likely silence

function generateSessionToken() {
  return `vad_${Date.now().toString(36)}_${(++sessionCounter).toString(36)}`
}

function notifyStateChange(state) {
  stateSubscribers.forEach(cb => {
    try { cb(state) } catch {}
  })
}

function transitionTo(newState) {
  if (!currentSession) return
  const current = currentSession.state
  const allowed = VALID_TRANSITIONS[current] || []
  if (!allowed.includes(newState)) {
    console.warn(`[VAD] invalid transition ${current} → ${newState}`)
    return false
  }
  currentSession.state = newState
  notifyStateChange(newState)
  return true
}

// ---------------------------------------------------------------------------
// Audio conversion & validation
// ---------------------------------------------------------------------------

function float32ToWav(samples) {
  const len = samples.length
  const buf = new ArrayBuffer(44 + len * 2)
  const dv = new DataView(buf)
  const sr = 16000
  const w = (off, v, sz) => {
    if (sz === 2) dv.setUint16(off, v, true)
    else dv.setUint32(off, v, true)
  }
  w(0, 0x46464952, 4); w(4, 36 + len * 2, 4); w(8, 0x45564157, 4)
  w(12, 0x20746d66, 4); w(16, 16, 4); w(20, 1, 2); w(22, 1, 2); w(24, sr, 4); w(28, sr * 2, 4); w(32, 2, 2); w(34, 16, 2)
  w(36, 0x61746164, 4); w(40, len * 2, 4)
  for (let i = 0; i < len; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    dv.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7FFF, true)
  }
  return new Blob([buf], { type: 'audio/wav' })
}

function isAudioValid(samples) {
  if (!samples || samples.length < MIN_SAMPLES) return false
  // Compute RMS to detect silence
  let sum = 0
  for (let i = 0; i < samples.length; i++) {
    sum += samples[i] * samples[i]
  }
  const rms = Math.sqrt(sum / samples.length)
  return rms >= MIN_RMS_THRESHOLD
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Subscribe to VAD state changes. Returns an unsubscribe function.
 */
export function subscribeVadState(callback) {
  stateSubscribers.add(callback)
  if (currentSession) {
    try { callback(currentSession.state) } catch {}
  }
  return () => stateSubscribers.delete(callback)
}

/**
 * Get current VAD state.
 */
export function getVadState() {
  return currentSession ? currentSession.state : VAD_STATE.IDLE
}

/**
 * Check if VAD is actively listening (not paused, not idle).
 */
export function isVadActive() {
  if (!currentSession) return false
  const s = currentSession.state
  return s === VAD_STATE.LISTENING || s === VAD_STATE.SPEECH_DETECTED
}

/**
 * Start VAD recording.
 *
 * @param {object} options
 * @param {function} options.onSpeechStart - Called when speech begins
 * @param {function} options.onSpeechEnd - Called with validated audio Blob when speech ends
 * @param {function} options.onError - Called on VAD error
 * @returns {Promise<{ ok: boolean, sessionToken?: string, error?: string }>}
 */
export async function startVadRecording({ onSpeechStart, onSpeechEnd, onError } = {}) {
  // Stop any existing session first
  if (currentSession) {
    stopVadRecording()
  }

  const sessionToken = generateSessionToken()
  currentSession = {
    token: sessionToken,
    callbacks: { onSpeechStart, onSpeechEnd, onError },
    state: VAD_STATE.IDLE,
    lastSpeechStart: 0,
  }

  transitionTo(VAD_STATE.INITIALIZING)

  try {
    const origin = window.location.origin
    const baseAssetPath = `${origin}/vad-assets/`
    const onnxWASMBasePath = `${origin}/vad-assets/onnx/`

    vadInstance = await MicVAD.new({
      baseAssetPath,
      onnxWASMBasePath,
      additionalAudioConstraints: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
        sampleRate: 16000,
      },
      positiveSpeechThreshold: 0.7,
      negativeSpeechThreshold: 0.35,
      minSpeechFrames: 6,
      preSpeechPadFrames: 10,
      onSpeechStart: () => {
        if (!currentSession || currentSession.token !== sessionToken) return
        if (!transitionTo(VAD_STATE.SPEECH_DETECTED)) return
        currentSession.lastSpeechStart = Date.now()
        if (currentSession.callbacks.onSpeechStart) {
          try { currentSession.callbacks.onSpeechStart() } catch {}
        }
      },
      onSpeechRealStart: () => {},
      onSpeechEnd: (audio) => {
        if (!currentSession || currentSession.token !== sessionToken) return
        // Validate audio before delivering
        if (!isAudioValid(audio)) {
          // Too short or silent — treat as misfire, return to listening
          transitionTo(VAD_STATE.LISTENING)
          return
        }
        transitionTo(VAD_STATE.LISTENING)
        if (currentSession.callbacks.onSpeechEnd) {
          try {
            currentSession.callbacks.onSpeechEnd(float32ToWav(audio))
          } catch {}
        }
      },
      onVADMisfire: () => {
        // Misfire = speech started but ended too quickly. Stay in listening.
        if (currentSession && currentSession.token === sessionToken) {
          transitionTo(VAD_STATE.LISTENING)
        }
      },
      onFrameProcessed: () => {},
      onError: (e) => {
        if (!currentSession || currentSession.token !== sessionToken) return
        transitionTo(VAD_STATE.ERROR)
        if (currentSession.callbacks.onError) {
          try { currentSession.callbacks.onError(e) } catch {}
        }
      },
      startOnLoad: true,
    })

    if (!currentSession || currentSession.token !== sessionToken) {
      // Session was stopped during init
      try { vadInstance.destroy() } catch {}
      vadInstance = null
      return { ok: false, error: 'session_cancelled' }
    }

    transitionTo(VAD_STATE.LISTENING)
    return { ok: true, sessionToken }
  } catch (e) {
    if (currentSession && currentSession.token === sessionToken) {
      transitionTo(VAD_STATE.ERROR)
      if (currentSession.callbacks.onError) {
        try { currentSession.callbacks.onError(e) } catch {}
      }
    }
    currentSession = null
    vadInstance = null
    return { ok: false, error: e?.message || 'init_failed' }
  }
}

/**
 * Stop VAD recording and clean up.
 */
export function stopVadRecording() {
  if (!currentSession) return

  transitionTo(VAD_STATE.STOPPING)

  const session = currentSession
  currentSession = null // Invalidate session token immediately

  if (vadInstance) {
    try { vadInstance.destroy() } catch {}
    vadInstance = null
  }

  transitionTo(VAD_STATE.IDLE)
  // Note: transitionTo won't work after currentSession = null, so notify directly
  notifyStateChange(VAD_STATE.IDLE)
}

/**
 * Pause VAD (keeps instance alive but stops processing).
 */
export function pauseVad() {
  if (!currentSession) return
  if (currentSession.state !== VAD_STATE.LISTENING &&
      currentSession.state !== VAD_STATE.SPEECH_DETECTED) return
  transitionTo(VAD_STATE.PAUSED)
  if (vadInstance) {
    try { vadInstance.pause() } catch {}
  }
}

/**
 * Resume VAD from paused state.
 */
export function resumeVad() {
  if (!currentSession) return
  if (currentSession.state !== VAD_STATE.PAUSED) return
  if (vadInstance) {
    try { vadInstance.start() } catch {}
  }
  transitionTo(VAD_STATE.LISTENING)
}
