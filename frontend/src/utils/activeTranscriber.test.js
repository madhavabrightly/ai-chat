import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  TRANSCRIBER_MODE,
  startVad,
  startBrowserSR,
  pause,
  resume,
  stopAll,
  subscribeTranscriberMode,
  getTranscriberMode,
  isTranscribing,
  subscribeActiveState,
  getActiveState,
  hasBrowserSpeechRecognition,
} from './activeTranscriber.js'

// Mock vadRecorder
vi.mock('./vadRecorder.js', () => ({
  VAD_STATE: Object.freeze({
    IDLE: 'idle',
    INITIALIZING: 'initializing',
    LISTENING: 'listening',
    SPEECH_DETECTED: 'speech_detected',
    PAUSED: 'paused',
    STOPPING: 'stopping',
    ERROR: 'error',
  }),
  startVadRecording: vi.fn(),
  stopVadRecording: vi.fn(),
  pauseVad: vi.fn(),
  resumeVad: vi.fn(),
  subscribeVadState: vi.fn(() => () => {}),
  getVadState: vi.fn(() => 'idle'),
  isVadActive: vi.fn(() => false),
}))

// Mock liveSpeechRecognition
vi.mock('./liveSpeechRecognition.js', () => ({
  startListening: vi.fn(),
  stopListening: vi.fn(),
  pauseListening: vi.fn(),
  resumeListening: vi.fn(),
  subscribeRecognitionState: vi.fn(() => () => {}),
  getRecognitionState: vi.fn(() => 'idle'),
  isSpeechRecognitionSupported: vi.fn(() => true),
}))

import * as vad from './vadRecorder.js'
import * as sr from './liveSpeechRecognition.js'

describe('activeTranscriber — mode management', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vad.startVadRecording.mockResolvedValue({ ok: true, sessionToken: 'vad_test' })
    sr.startListening.mockReturnValue({ ok: true })
    vad.getVadState.mockReturnValue('listening')
    sr.getRecognitionState.mockReturnValue('listening')
  })

  afterEach(async () => {
    await stopAll()
  })

  it('starts in IDLE mode', () => {
    expect(getTranscriberMode()).toBe(TRANSCRIBER_MODE.IDLE)
    expect(isTranscribing()).toBe(false)
  })

  it('startVad switches to VAD mode', async () => {
    const result = await startVad({})
    expect(result.ok).toBe(true)
    expect(result.mode).toBe(TRANSCRIBER_MODE.VAD)
    expect(getTranscriberMode()).toBe(TRANSCRIBER_MODE.VAD)
    expect(isTranscribing()).toBe(true)
  })

  it('startBrowserSR switches to BROWSER_SR mode', () => {
    const result = startBrowserSR({})
    expect(result.ok).toBe(true)
    expect(result.mode).toBe(TRANSCRIBER_MODE.BROWSER_SR)
    expect(getTranscriberMode()).toBe(TRANSCRIBER_MODE.BROWSER_SR)
  })

  it('startVad returns alreadyRunning when VAD is active', async () => {
    await startVad({})
    const result = await startVad({})
    expect(result.alreadyRunning).toBe(true)
  })

  it('startBrowserSR returns alreadyRunning when SR is active', () => {
    startBrowserSR({})
    const result = startBrowserSR({})
    expect(result.alreadyRunning).toBe(true)
  })

  it('starting VAD stops BROWSER_SR (mutual exclusion)', async () => {
    startBrowserSR({})
    expect(getTranscriberMode()).toBe(TRANSCRIBER_MODE.BROWSER_SR)

    await startVad({})
    expect(sr.stopListening).toHaveBeenCalled()
    expect(getTranscriberMode()).toBe(TRANSCRIBER_MODE.VAD)
  })

  it('starting BROWSER_SR stops VAD (mutual exclusion)', async () => {
    await startVad({})
    expect(getTranscriberMode()).toBe(TRANSCRIBER_MODE.VAD)

    startBrowserSR({})
    expect(vad.stopVadRecording).toHaveBeenCalled()
    expect(getTranscriberMode()).toBe(TRANSCRIBER_MODE.BROWSER_SR)
  })

  it('stopAll resets to IDLE', async () => {
    await startVad({})
    await stopAll()
    expect(getTranscriberMode()).toBe(TRANSCRIBER_MODE.IDLE)
    expect(isTranscribing()).toBe(false)
  })

  it('stopAll calls appropriate stop function for current mode', async () => {
    await startVad({})
    await stopAll()
    expect(vad.stopVadRecording).toHaveBeenCalled()

    startBrowserSR({})
    await stopAll()
    expect(sr.stopListening).toHaveBeenCalled()
  })
})

describe('activeTranscriber — pause/resume', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vad.startVadRecording.mockResolvedValue({ ok: true, sessionToken: 'vad_test' })
    sr.startListening.mockReturnValue({ ok: true })
  })

  afterEach(async () => {
    await stopAll()
  })

  it('pause delegates to VAD when in VAD mode', async () => {
    await startVad({})
    pause()
    expect(vad.pauseVad).toHaveBeenCalled()
    expect(sr.pauseListening).not.toHaveBeenCalled()
  })

  it('pause delegates to SR when in BROWSER_SR mode', () => {
    startBrowserSR({})
    pause()
    expect(sr.pauseListening).toHaveBeenCalled()
    expect(vad.pauseVad).not.toHaveBeenCalled()
  })

  it('resume delegates to VAD when in VAD mode', async () => {
    await startVad({})
    resume()
    expect(vad.resumeVad).toHaveBeenCalled()
  })

  it('resume delegates to SR when in BROWSER_SR mode', () => {
    startBrowserSR({})
    resume()
    expect(sr.resumeListening).toHaveBeenCalled()
  })

  it('pause is no-op when IDLE', () => {
    pause()
    expect(vad.pauseVad).not.toHaveBeenCalled()
    expect(sr.pauseListening).not.toHaveBeenCalled()
  })
})

describe('activeTranscriber — subscription', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vad.startVadRecording.mockResolvedValue({ ok: true, sessionToken: 'vad_test' })
  })

  afterEach(async () => {
    await stopAll()
  })

  it('subscribeTranscriberMode returns unsubscribe function', () => {
    const cb = vi.fn()
    const unsub = subscribeTranscriberMode(cb)
    expect(typeof unsub).toBe('function')
    unsub()
  })

  it('subscribeTranscriberMode immediately notifies current mode', () => {
    const cb = vi.fn()
    subscribeTranscriberMode(cb)
    expect(cb).toHaveBeenCalledWith(TRANSCRIBER_MODE.IDLE)
  })

  it('subscribeTranscriberMode notifies on mode change', async () => {
    const cb = vi.fn()
    const unsub = subscribeTranscriberMode(cb)
    cb.mockClear()

    await startVad({})
    expect(cb).toHaveBeenCalledWith(TRANSCRIBER_MODE.VAD)

    await stopAll()
    expect(cb).toHaveBeenCalledWith(TRANSCRIBER_MODE.IDLE)

    unsub()
  })

  it('subscribeActiveState returns combined unsubscribe', () => {
    const cb = vi.fn()
    const unsub = subscribeActiveState(cb)
    expect(typeof unsub).toBe('function')
    unsub()
  })

  it('getActiveState returns VAD state when in VAD mode', async () => {
    vad.getVadState.mockReturnValue('listening')
    await startVad({})
    expect(getActiveState()).toBe('listening')
  })

  it('getActiveState returns SR state when in BROWSER_SR mode', () => {
    sr.getRecognitionState.mockReturnValue('listening')
    startBrowserSR({})
    expect(getActiveState()).toBe('listening')
  })

  it('getActiveState returns idle when IDLE', () => {
    expect(getActiveState()).toBe('idle')
  })

  it('hasBrowserSpeechRecognition delegates to SR module', () => {
    sr.isSpeechRecognitionSupported.mockReturnValue(true)
    expect(hasBrowserSpeechRecognition()).toBe(true)

    sr.isSpeechRecognitionSupported.mockReturnValue(false)
    expect(hasBrowserSpeechRecognition()).toBe(false)
  })
})
