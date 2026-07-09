/**
 * Browser SpeechRecognition with silence detection and pause mode.
 * Prevents capturing AI's own voice by supporting pause/resume.
 */
let recognition = null
let onInterimCallback = null
let onFinalCallback = null
let isActive = false
let paused = false
let silenceTimer = null
let lastInterimTime = 0

const SILENCE_MS = 2000

export function isSpeechRecognitionSupported() {
  return !!(
    typeof window !== 'undefined' &&
    (window.SpeechRecognition || window.webkitSpeechRecognition)
  )
}

export function startListening({ onInterim, onFinal }) {
  if (!isSpeechRecognitionSupported()) return false

  stopListening()
  paused = false

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  recognition = new SpeechRecognition()
  recognition.continuous = true
  recognition.interimResults = true
  recognition.lang = 'en-US'
  recognition.maxAlternatives = 1

  onInterimCallback = onInterim || null
  onFinalCallback = onFinal || null
  isActive = true

  recognition.onresult = (event) => {
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
      lastInterimTime = Date.now()
      // Reset silence timer on new interim
      if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null }
      // Start silence timer
      silenceTimer = setTimeout(() => {
        if (isActive && !paused && interim) {
          // Treat as final after silence
          if (onFinalCallback) onFinalCallback(interim.trim())
        }
      }, SILENCE_MS)
      if (onInterimCallback) onInterimCallback(interim)
    }

    if (final) {
      if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null }
      if (onFinalCallback) onFinalCallback(final.trim())
    }
  }

  recognition.onerror = (event) => {
    if (event.error === 'not-allowed') {
      isActive = false
      if (onFinalCallback) onFinalCallback('__MIC_PERMISSION_DENIED__')
    }
  }

  recognition.onend = () => {
    // Only auto-restart if active and not paused
    if (isActive && !paused && recognition) {
      try { recognition.start() } catch {}
    }
  }

  try {
    recognition.start()
    return true
  } catch {
    return false
  }
}

export function pauseListening() {
  paused = true
  if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null }
  if (recognition) {
    try {
      recognition.onend = null
      recognition.stop()
    } catch {}
  }
}

export function resumeListening(opts) {
  if (opts) {
    if (opts.onInterim) onInterimCallback = opts.onInterim
    if (opts.onFinal) onFinalCallback = opts.onFinal
  }
  paused = false
  isActive = false // force restart
  if (recognition) {
    try { recognition.onend = null; recognition.stop() } catch {}
  }
  return startListening({ onInterim: onInterimCallback, onFinal: onFinalCallback })
}

export function stopListening() {
  paused = false
  isActive = false
  if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null }
  if (recognition) {
    try { recognition.onend = null; recognition.stop() } catch {}
    recognition = null
  }
  onInterimCallback = null
  onFinalCallback = null
}

export function isListening() {
  return isActive && !paused
}

export function isPaused() {
  return paused
}
