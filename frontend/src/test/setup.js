import '@testing-library/jest-dom'

// Override crypto.randomUUID for jsdom (jsdom provides its own implementation)
let uuidCounter = 0
Object.defineProperty(globalThis.crypto, 'randomUUID', {
  configurable: true,
  writable: true,
  value: () => `test-uuid-${++uuidCounter}`,
})

// Mock window.speechSynthesis
globalThis.window.speechSynthesis = {
  speak: () => {},
  cancel: () => {},
  pause: () => {},
  resume: () => {},
  getVoices: () => [],
  onvoiceschanged: null,
  speaking: false,
  pending: false,
  paused: false,
}

// Mock SpeechSynthesisUtterance
globalThis.window.SpeechSynthesisUtterance = class {
  constructor(text) {
    this.text = text
    this.voice = null
    this.rate = 1
    this.pitch = 1
    this.volume = 1
    this.onend = null
    this.onerror = null
    this.onstart = null
    this.onpause = null
    this.onresume = null
    this.onmark = null
    this.onboundary = null
  }
}

// Mock navigator.mediaDevices
if (!globalThis.navigator.mediaDevices) {
  globalThis.navigator.mediaDevices = {}
}
globalThis.navigator.mediaDevices.getUserMedia = async () => {
  throw new Error('getUserMedia not available in tests')
}
