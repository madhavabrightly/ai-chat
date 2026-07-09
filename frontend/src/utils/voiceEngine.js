/**
 * Browser TTS engine with proper gender-specific voice selection.
 * Waits for voiceschanged event, loads available voices, stores per-gender preferences.
 */
let voicesLoaded = false
let voiceList = []
let voiceListeners = []
let currentUtterance = null
let onEndCallback = null
let utteranceCounter = 0

const STORAGE_MALE = 'memoryTwin.preferredMaleVoice'
const STORAGE_FEMALE = 'memoryTwin.preferredFemaleVoice'

function getPreferredVoiceName(companionType) {
  const key = companionType === 'male' ? STORAGE_MALE : STORAGE_FEMALE
  try { return localStorage.getItem(key) } catch { return null }
}

function setPreferredVoiceName(companionType, name) {
  const key = companionType === 'male' ? STORAGE_MALE : STORAGE_FEMALE
  try { localStorage.setItem(key, name) } catch {}
}

export function loadBrowserVoices() {
  if (!window.speechSynthesis) return

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
    // Save the first match as preference
    setPreferredVoiceName(companionType, genderMatches[0].name)
    return genderMatches[0]
  }

  // Fallback: just use the first available voice
  if (voiceList.length > 0) return voiceList[0]

  return null
}

export function speakText(text, { companionType = 'female', preferredVoiceName, onEnd, onError } = {}) {
  stopSpeaking()

  if (!window.speechSynthesis) {
    if (onEnd) setTimeout(onEnd, 100)
    return
  }

  const utterance = new SpeechSynthesisUtterance(text)

  // Pick voice
  let voice = null
  if (preferredVoiceName) {
    voice = voiceList.find(v => v.name === preferredVoiceName)
  }
  if (!voice) {
    voice = pickVoiceForCompanion(companionType)
  }
  if (voice) utterance.voice = voice

  // Pitch/rate based on companion type
  utterance.rate = companionType === 'male' ? 0.92 : 0.94
  utterance.pitch = companionType === 'male' ? 0.88 : 1.08
  utterance.volume = 1

  const myId = ++utteranceCounter
  currentUtterance = { id: myId }
  onEndCallback = onEnd || null

  utterance.onstart = () => {}
  utterance.onend = () => {
    if (currentUtterance && currentUtterance.id === myId) {
      currentUtterance = null
      if (onEndCallback) {
        const cb = onEndCallback
        onEndCallback = null
        cb()
      }
    }
  }
  utterance.onerror = () => {
    if (currentUtterance && currentUtterance.id === myId) {
      currentUtterance = null
      if (onEndCallback) {
        const cb = onEndCallback
        onEndCallback = null
        cb()
      }
      if (onError) onError()
    }
  }

  window.speechSynthesis.speak(utterance)
}

export function stopSpeaking() {
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel()
  }
  if (onEndCallback) {
    const cb = onEndCallback
    onEndCallback = null
    setTimeout(cb, 50)
  }
  currentUtterance = null
}

export function isSpeaking() {
  return window.speechSynthesis ? window.speechSynthesis.speaking : false
}
