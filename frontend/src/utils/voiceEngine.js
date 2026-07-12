/**
 * Browser TTS engine with proper gender-specific voice selection.
 *
 * Key improvements:
 *   - Each speakText() call returns an operation ID and a cancel function
 *   - Separate onEnd / onCancel / onError callbacks (no shared callback)
 *   - Reactive state subscription via subscribeSpeaking()
 *   - Long text chunking to avoid browser TTS limits
 *   - Operation IDs prevent stale callbacks from firing after cancel
 */

import { avatarEventBus } from '../avatar/AvatarEventBus.js'

const STORAGE_MALE = 'memoryTwin.preferredMaleVoice'
const STORAGE_FEMALE = 'memoryTwin.preferredFemaleVoice'

// Maximum characters per chunk (Chrome SpeechSynthesis has a ~15s limit per utterance)
const MAX_CHUNK_CHARS = 200

// Watchdog timer: if an utterance doesn't complete in this time, force-complete
// Chromium sometimes loses the onend event for long or complex utterances.
const WATCHDOG_MS = 15000

// Module state
let voicesLoaded = false
let voiceList = []
let voiceListeners = []
let operationCounter = 0
let currentOperation = null // { id, utterance, callbacks, chunks, chunkIndex }
let speakingSubscribers = new Set()
let lastSpeakingState = false

function generateOperationId() {
  return `tts_${Date.now().toString(36)}_${(++operationCounter).toString(36)}`
}

function notifySpeakingChange(speaking) {
  if (lastSpeakingState === speaking) return
  lastSpeakingState = speaking
  speakingSubscribers.forEach(cb => {
    try { cb(speaking) } catch {}
  })
  avatarEventBus.emit('voice.energy', { speaking, energy: speaking ? 0.32 : 0 })
}

function emitSpeechBoundary(text, event) {
  const start = Number(event?.charIndex) || 0
  const tail = String(text || '').slice(start)
  const word = (tail.match(/[A-Za-z']+/) || [''])[0]
  const vowelCount = (word.match(/[aeiouy]/gi) || []).length
  const vowelRatio = word.length ? vowelCount / word.length : 0.25
  const lengthLift = Math.min(0.18, word.length * 0.018)
  avatarEventBus.emit('voice.energy', {
    speaking: true,
    energy: Math.min(1, 0.38 + vowelRatio * 0.44 + lengthLift),
    word: word.slice(0, 24),
    boundary: event?.name || 'word',
  })
}

function getPreferredVoiceName(companionType) {
  const key = companionType === 'male' ? STORAGE_MALE : STORAGE_FEMALE
  try { return localStorage.getItem(key) } catch { return null }
}

function setPreferredVoiceName(companionType, name) {
  const key = companionType === 'male' ? STORAGE_MALE : STORAGE_FEMALE
  try { localStorage.setItem(key, name) } catch {}
}

// ---------------------------------------------------------------------------
// Voice loading
// ---------------------------------------------------------------------------

export function loadBrowserVoices() {
  if (!window.speechSynthesis) return []

  const synth = window.speechSynthesis
  voiceList = synth.getVoices()

  if (voiceList.length > 0) {
    voicesLoaded = true
    voiceListeners.forEach(cb => cb(voiceList))
    voiceListeners = []
    return voiceList
  }

  // Wait for voiceschanged
  synth.onvoiceschanged = () => {
    voiceList = synth.getVoices()
    voicesLoaded = true
    voiceListeners.forEach(cb => cb(voiceList))
    voiceListeners = []
  }

  return []
}

export function getAvailableVoices() {
  if (!voicesLoaded) loadBrowserVoices()
  return voiceList
}

export function onVoicesReady(callback) {
  if (voicesLoaded && voiceList.length > 0) {
    callback(voiceList)
    return
  }
  voiceListeners.push(callback)
  if (!voicesLoaded) loadBrowserVoices()
}

export function pickVoiceForCompanion(companionType) {
  if (!voicesLoaded) loadBrowserVoices()

  const preferredName = getPreferredVoiceName(companionType)

  // Try saved preference first
  if (preferredName) {
    const found = voiceList.find(v => v.name === preferredName)
    if (found) return found
  }

  // Try gender-based voice name matching
  const genderKeyword = companionType === 'male' ? 'male' : 'female'
  const genderMatches = voiceList.filter(v =>
    v.name.toLowerCase().includes(genderKeyword)
  )

  if (genderMatches.length > 0) {
    setPreferredVoiceName(companionType, genderMatches[0].name)
    return genderMatches[0]
  }

  // Fallback: just use the first available voice
  if (voiceList.length > 0) return voiceList[0]

  return null
}

// ---------------------------------------------------------------------------
// Reactive state subscription
// ---------------------------------------------------------------------------

/**
 * Subscribe to speaking state changes. Returns an unsubscribe function.
 */
export function subscribeSpeaking(callback) {
  speakingSubscribers.add(callback)
  // Immediately notify current state
  try { callback(lastSpeakingState) } catch {}
  return () => speakingSubscribers.delete(callback)
}

/**
 * Get current speaking state (snapshot).
 */
export function isSpeaking() {
  return window.speechSynthesis ? window.speechSynthesis.speaking : false
}

// ---------------------------------------------------------------------------
// Text chunking
// ---------------------------------------------------------------------------

function chunkText(text) {
  if (!text) return []
  if (text.length <= MAX_CHUNK_CHARS) return [text]

  // Split on sentence boundaries, then re-pack into chunks
  const sentences = text.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [text]
  const chunks = []
  let current = ''
  for (const s of sentences) {
    if ((current + s).length > MAX_CHUNK_CHARS && current) {
      chunks.push(current.trim())
      current = s
    } else {
      current += s
    }
  }
  if (current.trim()) chunks.push(current.trim())
  return chunks.length > 0 ? chunks : [text]
}

// ---------------------------------------------------------------------------
// Speak / cancel
// ---------------------------------------------------------------------------

/**
 * Speak text with separate onEnd/onCancel/onError callbacks.
 *
 * @param {string} text - Text to speak
 * @param {object} options
 * @param {string} options.companionType - 'male' or 'female'
 * @param {string} options.preferredVoiceName - Override voice selection
 * @param {function} options.onStart - Called when first chunk starts
 * @param {function} options.onEnd - Called when all chunks complete naturally
 * @param {function} options.onCancel - Called when stopSpeaking() cancels this op
 * @param {function} options.onError - Called on speech synthesis error
 * @returns {{ id: string, cancel: function }}
 */
export function speakText(text, {
  companionType = 'female',
  preferredVoiceName,
  onStart,
  onEnd,
  onCancel,
  onError,
} = {}) {
  // Cancel any previous operation
  if (currentOperation) {
    const prev = currentOperation
    currentOperation = null
    try { prev.utterance.onend = null; prev.utterance.onerror = null } catch {}
    if (window.speechSynthesis) {
      try { window.speechSynthesis.cancel() } catch {}
    }
    if (prev.callbacks.onCancel) {
      try { prev.callbacks.onCancel() } catch {}
    }
  }

  const operationId = generateOperationId()

  if (!window.speechSynthesis) {
    // No TTS support — fire onEnd after a tick so callers can proceed
    setTimeout(() => { if (onEnd) try { onEnd() } catch {} }, 50)
    return { id: operationId, cancel: () => {} }
  }

  const chunks = chunkText(text)
  if (chunks.length === 0) {
    setTimeout(() => { if (onEnd) try { onEnd() } catch {} }, 50)
    return { id: operationId, cancel: () => {} }
  }

  // Pick voice once for all chunks
  let voice = null
  if (preferredVoiceName) {
    voice = voiceList.find(v => v.name === preferredVoiceName)
  }
  if (!voice) {
    voice = pickVoiceForCompanion(companionType)
  }

  const callbacks = { onStart, onEnd, onCancel, onError }
  const operation = {
    id: operationId,
    callbacks,
    chunks,
    chunkIndex: 0,
    utterance: null,
    cancelled: false,
    _watchdog: null,
  }
  currentOperation = operation

  const clearWatchdog = () => {
    if (operation._watchdog) {
      clearTimeout(operation._watchdog)
      operation._watchdog = null
    }
  }

  const speakChunk = (index) => {
    if (operation.cancelled || index >= chunks.length) {
      clearWatchdog()
      if (!operation.cancelled && operation === currentOperation) {
        currentOperation = null
        notifySpeakingChange(false)
        if (callbacks.onEnd) try { callbacks.onEnd() } catch {}
      }
      return
    }

    const utterance = new SpeechSynthesisUtterance(chunks[index])
    if (voice) utterance.voice = voice
    utterance.rate = companionType === 'male' ? 0.92 : 0.94
    utterance.pitch = companionType === 'male' ? 0.88 : 1.08
    utterance.volume = 1

    operation.utterance = utterance

    // Set watchdog for this chunk — browsers can lose onend events
    clearWatchdog()
    operation._watchdog = setTimeout(() => {
      if (operation.cancelled || operation !== currentOperation) return
      // Speech completion stalled — force complete
      operation.cancelled = true
      currentOperation = null
      if (window.speechSynthesis) {
        try { window.speechSynthesis.cancel() } catch {}
      }
      notifySpeakingChange(false)
      // Call onEnd (not onCancel) — this is a forced natural completion
      if (callbacks.onEnd) {
        try { callbacks.onEnd('timeout') } catch {}
      }
    }, WATCHDOG_MS)

    utterance.onstart = () => {
      if (operation.cancelled) return
      if (index === 0 && callbacks.onStart) {
        try { callbacks.onStart() } catch {}
      }
      notifySpeakingChange(true)
    }

    utterance.onboundary = (event) => emitSpeechBoundary(chunks[index], event)

    utterance.onend = () => {
      if (operation.cancelled) return
      clearWatchdog()
      speakChunk(index + 1)
    }

    utterance.onerror = (e) => {
      // 'canceled' / 'interrupted' errors are expected when we cancel
      if (e?.error === 'canceled' || e?.error === 'interrupted') return
      clearWatchdog()
      operation.cancelled = true
      currentOperation = null
      notifySpeakingChange(false)
      if (callbacks.onError) {
        try { callbacks.onError(e) } catch {}
      }
    }

    try {
      window.speechSynthesis.speak(utterance)
    } catch (e) {
      clearWatchdog()
      operation.cancelled = true
      currentOperation = null
      notifySpeakingChange(false)
      if (callbacks.onError) {
        try { callbacks.onError(e) } catch {}
      }
    }
  }

  speakChunk(0)

  return {
    id: operationId,
    cancel: () => stopSpeaking(operationId),
  }
}

/**
 * Create a queue-backed speech operation. New text can be enqueued while the
 * current utterance is already speaking, which lets live call audio start
 * before the complete model response has arrived.
 *
 * @returns {{ id: string, enqueue: function, close: function, cancel: function }}
 */
export function createSpeechQueue({
  companionType = 'female',
  preferredVoiceName,
  onStart,
  onEnd,
  onCancel,
  onError,
} = {}) {
  if (currentOperation) {
    const prev = currentOperation
    currentOperation = null
    try { prev.utterance.onend = null; prev.utterance.onerror = null } catch {}
    if (prev._watchdog) { clearTimeout(prev._watchdog); prev._watchdog = null }
    if (window.speechSynthesis) {
      try { window.speechSynthesis.cancel() } catch {}
    }
    if (prev.callbacks?.onCancel) {
      try { prev.callbacks.onCancel() } catch {}
    }
  }

  const operationId = generateOperationId()

  if (!window.speechSynthesis) {
    return {
      id: operationId,
      enqueue: () => {},
      close: () => { setTimeout(() => { if (onEnd) try { onEnd() } catch {} }, 50) },
      cancel: () => {},
    }
  }

  let voice = null
  if (preferredVoiceName) {
    voice = voiceList.find(v => v.name === preferredVoiceName)
  }
  if (!voice) {
    voice = pickVoiceForCompanion(companionType)
  }

  const callbacks = { onStart, onEnd, onCancel, onError }
  const operation = {
    id: operationId,
    callbacks,
    chunks: [],
    utterance: null,
    cancelled: false,
    closed: false,
    speaking: false,
    started: false,
    _watchdog: null,
  }
  currentOperation = operation

  const clearWatchdog = () => {
    if (operation._watchdog) {
      clearTimeout(operation._watchdog)
      operation._watchdog = null
    }
  }

  const finishIfClosed = () => {
    if (operation.cancelled || operation !== currentOperation) return true
    if (operation.closed && !operation.speaking && operation.chunks.length === 0) {
      clearWatchdog()
      currentOperation = null
      notifySpeakingChange(false)
      if (callbacks.onEnd) {
        try { callbacks.onEnd() } catch {}
      }
      return true
    }
    return false
  }

  const speakNext = () => {
    if (finishIfClosed()) return
    if (operation.speaking || operation.chunks.length === 0) return

    const chunk = operation.chunks.shift()
    const utterance = new SpeechSynthesisUtterance(chunk)
    if (voice) utterance.voice = voice
    utterance.rate = companionType === 'male' ? 0.94 : 0.96
    utterance.pitch = companionType === 'male' ? 0.88 : 1.08
    utterance.volume = 1

    operation.utterance = utterance
    operation.speaking = true

    clearWatchdog()
    operation._watchdog = setTimeout(() => {
      if (operation.cancelled || operation !== currentOperation) return
      operation.speaking = false
      speakNext()
      finishIfClosed()
    }, WATCHDOG_MS)

    utterance.onstart = () => {
      if (operation.cancelled || operation !== currentOperation) return
      if (!operation.started) {
        operation.started = true
        if (callbacks.onStart) {
          try { callbacks.onStart() } catch {}
        }
      }
      notifySpeakingChange(true)
    }

    utterance.onboundary = (event) => emitSpeechBoundary(chunk, event)

    utterance.onend = () => {
      if (operation.cancelled || operation !== currentOperation) return
      clearWatchdog()
      operation.speaking = false
      speakNext()
      finishIfClosed()
    }

    utterance.onerror = (e) => {
      if (e?.error === 'canceled' || e?.error === 'interrupted') return
      clearWatchdog()
      operation.cancelled = true
      currentOperation = null
      notifySpeakingChange(false)
      if (callbacks.onError) {
        try { callbacks.onError(e) } catch {}
      }
    }

    try {
      window.speechSynthesis.speak(utterance)
    } catch (e) {
      clearWatchdog()
      operation.cancelled = true
      currentOperation = null
      operation.speaking = false
      notifySpeakingChange(false)
      if (callbacks.onError) {
        try { callbacks.onError(e) } catch {}
      }
    }
  }

  return {
    id: operationId,
    enqueue: (text) => {
      if (operation.cancelled || operation !== currentOperation) return
      const pieces = chunkText(text)
      operation.chunks.push(...pieces)
      speakNext()
    },
    close: () => {
      if (operation.cancelled || operation !== currentOperation) return
      operation.closed = true
      finishIfClosed()
    },
    cancel: () => stopSpeaking(operationId),
  }
}

/**
 * Stop speaking. If operationId is provided, only cancel that operation.
 * Otherwise cancel any current operation.
 */
export function stopSpeaking(operationId = null) {
  if (!window.speechSynthesis) return

  if (operationId && currentOperation && currentOperation.id !== operationId) {
    return // Different operation — leave it alone
  }

  if (currentOperation) {
    const op = currentOperation
    op.cancelled = true
    if (op._watchdog) { clearTimeout(op._watchdog); op._watchdog = null }
    try { op.utterance.onend = null; op.utterance.onerror = null } catch {}
    currentOperation = null
    try { window.speechSynthesis.cancel() } catch {}
    notifySpeakingChange(false)
    if (op.callbacks.onCancel) {
      try { op.callbacks.onCancel() } catch {}
    }
  } else {
    try { window.speechSynthesis.cancel() } catch {}
    notifySpeakingChange(false)
  }
}
