import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  speakText,
  stopSpeaking,
  subscribeSpeaking,
  isSpeaking,
  pickVoiceForCompanion,
  loadBrowserVoices,
  getAvailableVoices,
} from './voiceEngine.js'

describe('voiceEngine — operation IDs and callbacks', () => {
  beforeEach(() => {
    localStorage.clear()
    // Reset speechSynthesis mock
    globalThis.window.speechSynthesis.speaking = false
    globalThis.window.speechSynthesis.pending = false
    globalThis.window.speechSynthesis.cancel = vi.fn()
    globalThis.window.speechSynthesis.speak = vi.fn()
    globalThis.window.speechSynthesis.getVoices = vi.fn(() => [
      { name: 'Google US English', lang: 'en-US' },
      { name: 'Microsoft Mark - English', lang: 'en-US' },
      { name: 'Microsoft Zira - English', lang: 'en-US' },
    ])
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('speakText returns an operation with id and cancel', () => {
    const op = speakText('Hello world', { companionType: 'female' })
    expect(op.id).toMatch(/^tts_/)
    expect(typeof op.cancel).toBe('function')
  })

  it('speakText calls speechSynthesis.speak', () => {
    speakText('Hello', { companionType: 'female' })
    expect(globalThis.window.speechSynthesis.speak).toHaveBeenCalled()
  })

  it('speakText fires onEnd after all chunks complete', async () => {
    const onEnd = vi.fn()
    const onCancel = vi.fn()
    const onError = vi.fn()

    // Capture the utterance passed to speak()
    let capturedUtterance = null
    globalThis.window.speechSynthesis.speak = vi.fn((u) => {
      capturedUtterance = u
    })

    speakText('Short text', {
      companionType: 'female',
      onEnd, onCancel, onError,
    })

    // Simulate utterance completion
    expect(capturedUtterance).toBeTruthy()
    capturedUtterance.onend?.()

    // Wait for next tick
    await new Promise(r => setTimeout(r, 10))
    expect(onEnd).toHaveBeenCalled()
    expect(onCancel).not.toHaveBeenCalled()
    expect(onError).not.toHaveBeenCalled()
  })

  it('speakText fires onCancel when stopSpeaking is called', () => {
    const onEnd = vi.fn()
    const onCancel = vi.fn()

    let capturedUtterance = null
    globalThis.window.speechSynthesis.speak = vi.fn((u) => {
      capturedUtterance = u
    })

    const op = speakText('Hello', {
      companionType: 'female',
      onEnd, onCancel,
    })

    op.cancel()

    expect(onCancel).toHaveBeenCalled()
    expect(onEnd).not.toHaveBeenCalled()
  })

  it('speakText fires onError on speech error', () => {
    const onError = vi.fn()
    const onEnd = vi.fn()

    let capturedUtterance = null
    globalThis.window.speechSynthesis.speak = vi.fn((u) => {
      capturedUtterance = u
    })

    speakText('Hello', {
      companionType: 'female',
      onEnd, onError,
    })

    capturedUtterance.onerror?.({ error: 'synthesis-failed' })

    expect(onError).toHaveBeenCalled()
    expect(onEnd).not.toHaveBeenCalled()
  })

  it('does not fire onError on canceled/interrupted errors', () => {
    const onError = vi.fn()

    let capturedUtterance = null
    globalThis.window.speechSynthesis.speak = vi.fn((u) => {
      capturedUtterance = u
    })

    speakText('Hello', {
      companionType: 'female',
      onError,
    })

    capturedUtterance.onerror?.({ error: 'canceled' })
    capturedUtterance.onerror?.({ error: 'interrupted' })

    expect(onError).not.toHaveBeenCalled()
  })

  it('cancels previous operation when new speakText is called', () => {
    const onCancel1 = vi.fn()
    const onCancel2 = vi.fn()

    speakText('First', { companionType: 'female', onCancel: onCancel1 })
    speakText('Second', { companionType: 'female', onCancel: onCancel2 })

    expect(onCancel1).toHaveBeenCalled()
  })

  it('stopSpeaking with operationId only cancels matching op', () => {
    const onCancel1 = vi.fn()
    const onCancel2 = vi.fn()

    const op1 = speakText('First', { companionType: 'female', onCancel: onCancel1 })
    speakText('Second', { companionType: 'female', onCancel: onCancel2 })

    // op1 is no longer current — stopSpeaking(op1.id) should be a no-op
    stopSpeaking(op1.id)
    expect(onCancel2).not.toHaveBeenCalled()
  })

  it('stopSpeaking without id cancels current op', () => {
    const onCancel = vi.fn()
    speakText('Hello', { companionType: 'female', onCancel })
    stopSpeaking()
    expect(onCancel).toHaveBeenCalled()
  })
})

describe('voiceEngine — reactive subscription', () => {
  beforeEach(() => {
    localStorage.clear()
    globalThis.window.speechSynthesis.speaking = false
    globalThis.window.speechSynthesis.cancel = vi.fn()
    globalThis.window.speechSynthesis.speak = vi.fn()
    globalThis.window.speechSynthesis.getVoices = vi.fn(() => [])
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('subscribeSpeaking returns unsubscribe function', () => {
    const cb = vi.fn()
    const unsub = subscribeSpeaking(cb)
    expect(typeof unsub).toBe('function')
    unsub()
  })

  it('subscribeSpeaking immediately notifies current state', () => {
    const cb = vi.fn()
    subscribeSpeaking(cb)
    expect(cb).toHaveBeenCalledWith(false)
  })

  it('subscribeSpeaking notifies on speaking change', () => {
    const cb = vi.fn()
    subscribeSpeaking(cb)
    cb.mockClear()

    let capturedUtterance = null
    globalThis.window.speechSynthesis.speak = vi.fn((u) => {
      capturedUtterance = u
    })

    speakText('Hello', { companionType: 'female' })
    capturedUtterance.onstart?.()

    expect(cb).toHaveBeenCalledWith(true)
  })

  it('unsubscribe stops notifications', () => {
    const cb = vi.fn()
    const unsub = subscribeSpeaking(cb)
    cb.mockClear()
    unsub()

    let capturedUtterance = null
    globalThis.window.speechSynthesis.speak = vi.fn((u) => {
      capturedUtterance = u
    })

    speakText('Hello', { companionType: 'female' })
    capturedUtterance.onstart?.()

    expect(cb).not.toHaveBeenCalled()
  })
})

describe('voiceEngine — voice selection', () => {
  beforeEach(() => {
    localStorage.clear()
    globalThis.window.speechSynthesis.getVoices = vi.fn(() => [
      { name: 'Google US English', lang: 'en-US' },
      { name: 'Microsoft Mark - English (Male)', lang: 'en-US' },
      { name: 'Microsoft Zira - English (Female)', lang: 'en-US' },
    ])
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('pickVoiceForCompanion returns male voice for male companion', () => {
    loadBrowserVoices()
    const voice = pickVoiceForCompanion('male')
    expect(voice.name.toLowerCase()).toContain('male')
  })

  it('pickVoiceForCompanion returns female voice for female companion', () => {
    loadBrowserVoices()
    const voice = pickVoiceForCompanion('female')
    expect(voice.name.toLowerCase()).toContain('female')
  })

  it('pickVoiceForCompanion uses saved preference', () => {
    localStorage.setItem('memoryTwin.preferredFemaleVoice', 'Google US English')
    loadBrowserVoices()
    const voice = pickVoiceForCompanion('female')
    expect(voice.name).toBe('Google US English')
  })

  it('pickVoiceForCompanion falls back to first voice when no match', () => {
    globalThis.window.speechSynthesis.getVoices = vi.fn(() => [
      { name: 'Generic Voice', lang: 'en-US' },
    ])
    loadBrowserVoices()
    const voice = pickVoiceForCompanion('female')
    expect(voice.name).toBe('Generic Voice')
  })
})
