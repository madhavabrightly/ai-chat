/**
 * Browser SpeechRecognition fallback for environments where VAD is unavailable.
 *
 * This module is mutually exclusive with vadRecorder.js — only one should be
 * active at a time. The LiveCallScreen coordinates this via the activeTranscriber
 * module.
 *
 * State machine:
 *   idle → starting → listening → paused → listening → ... → stopping → idle
 *   any state → error → idle
 *
 * Key improvements:
 *   - Explicit state machine
 *   - Session token prevents stale callbacks
 *   - Separate onEnd / onError / onCancel semantics
 *   - Reactive state subscription
 *   - Fast silence detection with debounced finalization
 */

const SILENCE_MS = 750
const DUPLICATE_FINAL_WINDOW_MS = 1400

// States
const STATE = Object.freeze({
  IDLE: 'idle',
  STARTING: 'starting',
  LISTENING: 'listening',
  PAUSED: 'paused',
  STOPPING: 'stopping',
  ERROR: 'error',
})

const VALID_TRANSITIONS = {
  [STATE.IDLE]: [STATE.STARTING],
  [STATE.STARTING]: [STATE.LISTENING, STATE.ERROR, STATE.IDLE],
  [STATE.LISTENING]: [STATE.PAUSED, STATE.STOPPING, STATE.ERROR],
  [STATE.PAUSED]: [STATE.LISTENING, STATE.STOPPING, STATE.ERROR],
  [STATE.STOPPING]: [STATE.IDLE, STATE.ERROR],
  [STATE.ERROR]: [STATE.IDLE, STATE.STARTING],
}

// Module state
let recognition = null
let currentSession = null
let stateSubscribers = new Set()
let sessionCounter = 0

function generateSessionToken() {
  return `sr_${Date.now().toString(36)}_${(++sessionCounter).toString(36)}`
}

function notifyStateChange(state) {
  stateSubscribers.forEach(cb => {
    try { cb(state) } catch {}
  })
}

function transitionTo(newState) {
  if (!currentSession) return false
  const current = currentSession.state
  const allowed = VALID_TRANSITIONS[current] || []
  if (!allowed.includes(newState)) {
    console.warn(`[SR] invalid transition ${current} → ${newState}`)
    return false
  }
  currentSession.state = newState
  notifyStateChange(newState)
  return true
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function isSpeechRecognitionSupported() {
  return !!(
    typeof window !== 'undefined' &&
    (window.SpeechRecognition || window.webkitSpeechRecognition)
  )
}

export function subscribeRecognitionState(callback) {
  stateSubscribers.add(callback)
  if (currentSession) {
    try { callback(currentSession.state) } catch {}
  }
  return () => stateSubscribers.delete(callback)
}

export function getRecognitionState() {
  return currentSession ? currentSession.state : STATE.IDLE
}

export function isListening() {
  return currentSession?.state === STATE.LISTENING
}

export function isPaused() {
  return currentSession?.state === STATE.PAUSED
}

/**
 * Start listening with browser SpeechRecognition.
 *
 * @param {object} options
 * @param {function} options.onSpeechStart - Called once when a fresh utterance starts
 * @param {function} options.onInterim - Called with interim transcript
 * @param {function} options.onFinal - Called with final transcript
 * @param {function} options.onError - Called on error
 * @returns {{ ok: boolean, sessionToken?: string, error?: string }}
 */
export function startListening({ onSpeechStart, onInterim, onFinal, onError } = {}) {
  if (!isSpeechRecognitionSupported()) {
    return { ok: false, error: 'not_supported' }
  }

  // Stop any existing session
  if (currentSession) {
    stopListening()
  }

  const sessionToken = generateSessionToken()
  currentSession = {
    token: sessionToken,
    callbacks: { onSpeechStart, onInterim, onFinal, onError },
    state: STATE.IDLE,
    silenceTimer: null,
    pendingTranscript: '',
    speechStarted: false,
    lastFinalText: '',
    lastFinalAt: 0,
  }

  transitionTo(STATE.STARTING)

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  recognition = new SpeechRecognition()
  recognition.continuous = true
  recognition.interimResults = true
  recognition.lang = 'en-US'
  recognition.maxAlternatives = 1

  const markSpeechStarted = () => {
    if (!currentSession || currentSession.token !== sessionToken) return
    if (currentSession.speechStarted) return
    currentSession.speechStarted = true
    if (currentSession.callbacks.onSpeechStart) {
      try { currentSession.callbacks.onSpeechStart() } catch {}
    }
  }

  const commitTranscript = (text, reason = 'final') => {
    if (!currentSession || currentSession.token !== sessionToken) return
    const transcript = String(text || '').replace(/\s+/g, ' ').trim()
    if (!transcript) return

    const now = Date.now()
    const sameAsLast = transcript.toLowerCase() === currentSession.lastFinalText.toLowerCase()
    if (sameAsLast && now - currentSession.lastFinalAt < DUPLICATE_FINAL_WINDOW_MS) {
      return
    }

    if (currentSession.silenceTimer) {
      clearTimeout(currentSession.silenceTimer)
      currentSession.silenceTimer = null
    }
    currentSession.pendingTranscript = ''
    currentSession.speechStarted = false
    currentSession.lastFinalText = transcript
    currentSession.lastFinalAt = now

    if (currentSession.callbacks.onFinal) {
      try { currentSession.callbacks.onFinal(transcript, { reason }) } catch {}
    }
  }

  const scheduleSilenceCommit = () => {
    if (!currentSession || currentSession.token !== sessionToken) return
    if (currentSession.silenceTimer) {
      clearTimeout(currentSession.silenceTimer)
      currentSession.silenceTimer = null
    }
    currentSession.silenceTimer = setTimeout(() => {
      if (!currentSession || currentSession.token !== sessionToken) return
      if (currentSession.state !== STATE.LISTENING) return
      commitTranscript(currentSession.pendingTranscript, 'silence')
    }, SILENCE_MS)
  }

  recognition.onresult = (event) => {
    if (!currentSession || currentSession.token !== sessionToken) return
    let interim = ''
    let final = ''

    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript
      if (event.results[i].isFinal) {
        final += transcript
      } else {
        interim += transcript
      }
    }

    if (interim) {
      markSpeechStarted()
      currentSession.pendingTranscript = interim
      scheduleSilenceCommit()
      if (currentSession.callbacks.onInterim) {
        try { currentSession.callbacks.onInterim(interim) } catch {}
      }
    }

    if (final) {
      markSpeechStarted()
      commitTranscript(final, 'final')
    }
  }

  recognition.onerror = (event) => {
    if (!currentSession || currentSession.token !== sessionToken) return
    if (event.error === 'not-allowed') {
      transitionTo(STATE.ERROR)
      if (currentSession.callbacks.onError) {
        try { currentSession.callbacks.onError({ code: 'MIC_PERMISSION_DENIED', message: 'Microphone permission denied' }) } catch {}
      }
    } else if (event.error === 'no-speech') {
      // Common, non-fatal — stay in listening
      return
    } else {
      transitionTo(STATE.ERROR)
      if (currentSession.callbacks.onError) {
        try { currentSession.callbacks.onError({ code: event.error, message: event.error }) } catch {}
      }
    }
  }

  recognition.onend = () => {
    if (!currentSession || currentSession.token !== sessionToken) return
    // Auto-restart if still in listening state
    if (currentSession.state === STATE.LISTENING && recognition) {
      try { recognition.start() } catch {}
    }
  }

  try {
    recognition.start()
    transitionTo(STATE.LISTENING)
    return { ok: true, sessionToken }
  } catch (e) {
    transitionTo(STATE.ERROR)
    if (currentSession.callbacks.onError) {
      try { currentSession.callbacks.onError({ code: 'START_FAILED', message: e.message }) } catch {}
    }
    return { ok: false, error: e.message }
  }
}

/**
 * Pause listening (keeps recognition alive but stops processing).
 */
export function pauseListening() {
  if (!currentSession) return
  if (currentSession.state !== STATE.LISTENING) return
  if (currentSession.silenceTimer) {
    clearTimeout(currentSession.silenceTimer)
    currentSession.silenceTimer = null
  }
  transitionTo(STATE.PAUSED)
  if (recognition) {
    try {
      recognition.onend = null
      recognition.stop()
    } catch {}
  }
}

/**
 * Resume listening from paused state.
 */
export function resumeListening(opts) {
  if (!currentSession) return { ok: false, error: 'no_session' }
  if (opts) {
    if (opts.onSpeechStart) currentSession.callbacks.onSpeechStart = opts.onSpeechStart
    if (opts.onInterim) currentSession.callbacks.onInterim = opts.onInterim
    if (opts.onFinal) currentSession.callbacks.onFinal = opts.onFinal
  }
  if (currentSession.state !== STATE.PAUSED) return { ok: false, error: 'not_paused' }
  // Force restart
  if (recognition) {
    try { recognition.onend = null; recognition.stop() } catch {}
  }
  return startListening({
    onSpeechStart: currentSession.callbacks.onSpeechStart,
    onInterim: currentSession.callbacks.onInterim,
    onFinal: currentSession.callbacks.onFinal,
    onError: currentSession.callbacks.onError,
  })
}

/**
 * Stop listening and clean up.
 */
export function stopListening() {
  if (!currentSession) return

  transitionTo(STATE.STOPPING)

  const session = currentSession
  currentSession = null // Invalidate session token

  if (session.silenceTimer) {
    clearTimeout(session.silenceTimer)
    session.silenceTimer = null
  }
  if (recognition) {
    try {
      recognition.onend = null
      recognition.onresult = null
      recognition.onerror = null
      recognition.stop()
    } catch {}
    recognition = null
  }

  notifyStateChange(STATE.IDLE)
}
