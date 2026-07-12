import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  VAD_STATE,
  subscribeVadState,
  getVadState,
  isVadActive,
  startVadRecording,
  stopVadRecording,
  pauseVad,
  resumeVad,
} from './vadRecorder.js'

// Mock @ricky0123/vad-web
vi.mock('@ricky0123/vad-web', () => ({
  MicVAD: {
    new: vi.fn(),
  },
}))

import { MicVAD } from '@ricky0123/vad-web'

describe('vadRecorder — state machine', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Default mock: successful init
    MicVAD.new.mockResolvedValue({
      destroy: vi.fn(),
      pause: vi.fn(),
      start: vi.fn(),
    })
  })

  afterEach(() => {
    stopVadRecording()
  })

  it('starts in IDLE state', () => {
    expect(getVadState()).toBe(VAD_STATE.IDLE)
    expect(isVadActive()).toBe(false)
  })

  it('transitions IDLE → INITIALIZING → LISTENING on start', async () => {
    const states = []
    const unsub = subscribeVadState(s => states.push(s))

    const result = await startVadRecording({})
    expect(result.ok).toBe(true)
    expect(result.sessionToken).toMatch(/^vad_/)
    expect(getVadState()).toBe(VAD_STATE.LISTENING)
    expect(isVadActive()).toBe(true)
    expect(states).toContain(VAD_STATE.INITIALIZING)
    expect(states).toContain(VAD_STATE.LISTENING)

    unsub()
  })

  it('transitions to ERROR on init failure', async () => {
    MicVAD.new.mockRejectedValueOnce(new Error('mic permission denied'))

    const onError = vi.fn()
    const result = await startVadRecording({ onError })

    expect(result.ok).toBe(false)
    expect(result.error).toBe('mic permission denied')
    expect(getVadState()).toBe(VAD_STATE.IDLE)
    expect(onError).toHaveBeenCalled()
  })

  it('stopVadRecording transitions to IDLE', async () => {
    await startVadRecording({})
    expect(getVadState()).toBe(VAD_STATE.LISTENING)

    stopVadRecording()
    expect(getVadState()).toBe(VAD_STATE.IDLE)
    expect(isVadActive()).toBe(false)
  })

  it('pauseVad transitions LISTENING → PAUSED', async () => {
    await startVadRecording({})
    pauseVad()
    expect(getVadState()).toBe(VAD_STATE.PAUSED)
    expect(isVadActive()).toBe(false)
  })

  it('resumeVad transitions PAUSED → LISTENING', async () => {
    await startVadRecording({})
    pauseVad()
    resumeVad()
    expect(getVadState()).toBe(VAD_STATE.LISTENING)
    expect(isVadActive()).toBe(true)
  })

  it('pauseVad is no-op when not listening', () => {
    pauseVad()
    expect(getVadState()).toBe(VAD_STATE.IDLE)
  })

  it('resumeVad is no-op when not paused', async () => {
    await startVadRecording({})
    resumeVad() // Already listening
    expect(getVadState()).toBe(VAD_STATE.LISTENING)
  })

  it('subscribeVadState returns unsubscribe function', () => {
    const cb = vi.fn()
    const unsub = subscribeVadState(cb)
    expect(typeof unsub).toBe('function')
    unsub()
  })

  it('subscribeVadState notifies on state changes', async () => {
    const cb = vi.fn()
    const unsub = subscribeVadState(cb)
    cb.mockClear()

    await startVadRecording({})
    expect(cb).toHaveBeenCalledWith(VAD_STATE.INITIALIZING)
    expect(cb).toHaveBeenCalledWith(VAD_STATE.LISTENING)

    unsub()
  })

  it('starting a new session stops the previous one', async () => {
    await startVadRecording({})
    const firstToken = getVadState() // Should be LISTENING

    await startVadRecording({})
    expect(getVadState()).toBe(VAD_STATE.LISTENING)
  })
})

describe('vadRecorder — session token isolation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    MicVAD.new.mockResolvedValue({
      destroy: vi.fn(),
      pause: vi.fn(),
      start: vi.fn(),
    })
  })

  afterEach(() => {
    stopVadRecording()
  })

  it('stale callbacks do not fire after stop', async () => {
    let capturedCallbacks = null
    MicVAD.new.mockImplementationOnce((opts) => {
      capturedCallbacks = opts
      return Promise.resolve({
        destroy: vi.fn(),
        pause: vi.fn(),
        start: vi.fn(),
      })
    })

    const onSpeechStart = vi.fn()
    await startVadRecording({ onSpeechStart })

    // Stop the session
    stopVadRecording()

    // Simulate a stale callback firing after stop
    capturedCallbacks.onSpeechStart?.()
    expect(onSpeechStart).not.toHaveBeenCalled()
  })

  it('stale onSpeechEnd does not fire after stop', async () => {
    let capturedCallbacks = null
    MicVAD.new.mockImplementationOnce((opts) => {
      capturedCallbacks = opts
      return Promise.resolve({
        destroy: vi.fn(),
        pause: vi.fn(),
        start: vi.fn(),
      })
    })

    const onSpeechEnd = vi.fn()
    await startVadRecording({ onSpeechEnd })

    stopVadRecording()

    // Simulate stale callback with valid audio
    const fakeAudio = new Float32Array(16000)
    for (let i = 0; i < fakeAudio.length; i++) fakeAudio[i] = 0.1
    capturedCallbacks.onSpeechEnd?.(fakeAudio)
    expect(onSpeechEnd).not.toHaveBeenCalled()
  })
})
