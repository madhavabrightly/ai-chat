import { avatarEventBus } from './AvatarEventBus.js'

export class LipSyncController {
  constructor() {
    this.audioContext = null
    this.analyser = null
    this.data = null
    this.source = null
    this.speaking = false
    this.amplitude = 0
    this.targetAmplitude = 0
    this.clock = 0
    this.boundaryEnergy = 0
    this.boundaryAt = 0
    this.unsubscribeVoiceEnergy = avatarEventBus.on('voice.energy', (event) => {
      this.boundaryEnergy = Math.max(0, Math.min(1, Number(event.energy) || 0))
      this.boundaryAt = performance.now()
    })
  }

  attachAnalyser(analyser) {
    this.analyser = analyser
    this.data = new Uint8Array(analyser.frequencyBinCount)
  }

  attachAudioElement(audioElement) {
    if (!audioElement || typeof AudioContext === 'undefined') return false
    this.disposeAudioSource()
    this.audioContext = this.audioContext || new AudioContext()
    this.source = this.audioContext.createMediaElementSource(audioElement)
    this.attachAnalyser(this.audioContext.createAnalyser())
    this.analyser.fftSize = 512
    this.source.connect(this.analyser)
    this.analyser.connect(this.audioContext.destination)
    return true
  }

  attachMediaStream(stream) {
    if (!stream || typeof AudioContext === 'undefined') return false
    this.disposeAudioSource()
    this.audioContext = this.audioContext || new AudioContext()
    this.source = this.audioContext.createMediaStreamSource(stream)
    this.attachAnalyser(this.audioContext.createAnalyser())
    this.analyser.fftSize = 512
    this.source.connect(this.analyser)
    return true
  }

  setSpeaking(value) {
    this.speaking = Boolean(value)
    if (!this.speaking) this.targetAmplitude = 0
  }

  update(delta, elapsedSeconds = 0, intensity = 1) {
    this.clock += delta
    if (this.analyser && this.data) {
      this.analyser.getByteFrequencyData(this.data)
      let total = 0
      const start = 2
      const end = Math.min(this.data.length, 42)
      for (let i = start; i < end; i += 1) total += this.data[i]
      this.targetAmplitude = Math.min(1, (total / Math.max(1, end - start)) / 120)
    } else if (this.speaking && performance.now() - this.boundaryAt < 180) {
      this.targetAmplitude = Math.min(1, this.boundaryEnergy * intensity)
    } else if (this.speaking) {
      const syllable = Math.sin(elapsedSeconds * 19.5) * 0.5 + 0.5
      const smallMotion = Math.sin(elapsedSeconds * 43.0) * 0.18 + 0.18
      this.targetAmplitude = Math.min(1, (0.2 + syllable * 0.58 + smallMotion) * intensity)
    } else {
      this.targetAmplitude = 0
    }

    const speed = this.targetAmplitude > this.amplitude ? 18 : 10
    const alpha = 1 - Math.exp(-speed * delta)
    this.amplitude += (this.targetAmplitude - this.amplitude) * alpha
    return this.amplitude
  }

  disposeAudioSource() {
    if (this.source) {
      try { this.source.disconnect() } catch {}
      this.source = null
    }
    if (this.analyser) {
      try { this.analyser.disconnect() } catch {}
      this.analyser = null
    }
    this.data = null
  }

  dispose() {
    this.unsubscribeVoiceEnergy?.()
    this.unsubscribeVoiceEnergy = null
    this.disposeAudioSource()
    if (this.audioContext) {
      try { this.audioContext.close() } catch {}
      this.audioContext = null
    }
  }
}
