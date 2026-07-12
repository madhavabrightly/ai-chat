/**
 * Coordinator that ensures only ONE transcription pipeline runs at a time.
 *
 * The Memory Twin app has two transcription paths:
 *   1. VAD-based (vadRecorder.js) — preferred, gives us audio chunks for ASR
 *   2. Browser SpeechRecognition (liveSpeechRecognition.js) — fallback
 *
 * This module enforces mutual exclusion: starting one stops the other.
 */

import {
  startVadRecording,
  stopVadRecording,
  pauseVad,
  resumeVad,
  subscribeVadState,
  getVadState,
  isVadActive,
  VAD_STATE,
} from './vadRecorder.js'

import {
  startListening,
  stopListening,
  pauseListening,
  resumeListening,
  subscribeRecognitionState,
  getRecognitionState,
  isSpeechRecognitionSupported,
} from './liveSpeechRecognition.js'

export const TRANSCRIBER_MODE = Object.freeze({
  IDLE: 'idle',
  VAD: 'vad',
  BROWSER_SR: 'browser_sr',
})

let currentMode = TRANSCRIBER_MODE.IDLE
let modeSubscribers = new Set()

function notifyModeChange(mode) {
  modeSubscribers.forEach(cb => {
    try { cb(mode) } catch {}
  })
}

export function subscribeTranscriberMode(callback) {
  modeSubscribers.add(callback)
  try { callback(currentMode) } catch {}
  return () => modeSubscribers.delete(callback)
}

export function getTranscriberMode() {
  return currentMode
}

export function isTranscribing() {
  return currentMode !== TRANSCRIBER_MODE.IDLE
}

/**
 * Start VAD-based transcription. Stops any other mode first.
 */
export async function startVad(opts) {
  if (currentMode === TRANSCRIBER_MODE.VAD) {
    return { ok: true, mode: TRANSCRIBER_MODE.VAD, alreadyRunning: true }
  }
  // Stop any other mode
  await stopAll()

  const result = await startVadRecording(opts)
  if (result.ok) {
    currentMode = TRANSCRIBER_MODE.VAD
    notifyModeChange(currentMode)
  }
  return { ...result, mode: currentMode }
}

/**
 * Start browser SpeechRecognition. Stops any other mode first.
 */
export function startBrowserSR(opts) {
  if (currentMode === TRANSCRIBER_MODE.BROWSER_SR) {
    return { ok: true, mode: TRANSCRIBER_MODE.BROWSER_SR, alreadyRunning: true }
  }
  stopAll()

  const result = startListening(opts)
  if (result.ok) {
    currentMode = TRANSCRIBER_MODE.BROWSER_SR
    notifyModeChange(currentMode)
  }
  return { ...result, mode: currentMode }
}

/**
 * Pause current transcription (whichever mode is active).
 */
export function pause() {
  if (currentMode === TRANSCRIBER_MODE.VAD) pauseVad()
  else if (currentMode === TRANSCRIBER_MODE.BROWSER_SR) pauseListening()
}

/**
 * Resume current transcription.
 */
export function resume(opts) {
  if (currentMode === TRANSCRIBER_MODE.VAD) resumeVad()
  else if (currentMode === TRANSCRIBER_MODE.BROWSER_SR) resumeListening(opts)
}

/**
 * Stop all transcription and clean up.
 */
export async function stopAll() {
  if (currentMode === TRANSCRIBER_MODE.VAD) {
    stopVadRecording()
  } else if (currentMode === TRANSCRIBER_MODE.BROWSER_SR) {
    stopListening()
  }
  currentMode = TRANSCRIBER_MODE.IDLE
  notifyModeChange(currentMode)
}

/**
 * Subscribe to state changes from the active transcriber.
 * Returns an unsubscribe function.
 */
export function subscribeActiveState(callback) {
  const unsubVad = subscribeVadState(callback)
  const unsubSR = subscribeRecognitionState(callback)
  return () => {
    unsubVad()
    unsubSR()
  }
}

/**
 * Get current state from the active transcriber.
 */
export function getActiveState() {
  if (currentMode === TRANSCRIBER_MODE.VAD) return getVadState()
  if (currentMode === TRANSCRIBER_MODE.BROWSER_SR) return getRecognitionState()
  return 'idle'
}

/**
 * Check if browser SpeechRecognition is available (for fallback decision).
 */
export function hasBrowserSpeechRecognition() {
  return isSpeechRecognitionSupported()
}

export { VAD_STATE }
