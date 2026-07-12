import { LoopOnce, MathUtils } from 'three'
import { buildAnimationRegistry, resolveAvatarAction } from './AnimationRegistry.js'
import { FacialController } from './FacialController.js'
import { LipSyncController } from './LipSyncController.js'
import { ProceduralRigController } from './ProceduralRigController.js'

const LACRIMOSA_IDLE_HOLD_SECONDS = 1.35

export class AvatarController {
  constructor({ scene, actions = {}, animations = [] }) {
    this.scene = scene
    this.actions = actions
    this.registry = buildAnimationRegistry(animations)
    this.facial = new FacialController(scene)
    this.rig = new ProceduralRigController(scene)
    this.lipSync = new LipSyncController()
    this.currentClip = null
    this.resolvedAction = resolveAvatarAction({ registry: this.registry })
    this.rootSway = 0
    this.basePositionY = scene?.position?.y || 0
    this.playClip(this.resolvedAction.clipName)
    if (!this.currentClip) this.currentClip = 'live-pose'
  }

  playClip(clipName) {
    if (!clipName || this.currentClip === clipName) return
    const next = this.actions[clipName] || this.actions[Object.keys(this.actions)[0]]
    if (!next) return

    next.enabled = true
    next.setLoop(LoopOnce, 1)
    next.clampWhenFinished = true
    next.timeScale = 0
    next.reset().fadeIn(0.15).play()
    next.time = getHoldPoseTime(next.getClip?.()?.duration)
    next.getMixer?.().setTime(next.time)
    next.paused = true

    if (this.currentClip && this.actions[this.currentClip] && this.actions[this.currentClip] !== next) {
      this.actions[this.currentClip].fadeOut(0.25)
    }
    this.currentClip = clipName
  }

  applyState({ state, mood, isSpeaking, plan }) {
    this.resolvedAction = resolveAvatarAction({
      state,
      mood,
      isSpeaking,
      plan,
      registry: this.registry,
    })
    this.playClip(this.resolvedAction.clipName)
    this.facial.setExpression(this.resolvedAction.expression)
    this.lipSync.setSpeaking(isSpeaking)
  }

  attachAudioElement(audioElement) {
    return this.lipSync.attachAudioElement(audioElement)
  }

  attachMediaStream(stream) {
    return this.lipSync.attachMediaStream(stream)
  }

  update(delta, elapsed) {
    const pose = this.resolvedAction?.pose || {}
    const energy = pose.energy || 0.2
    const mouthAmplitude = this.lipSync.update(delta, elapsed, Math.max(0.35, energy))
    const idleSway = Math.sin(elapsed * 0.8) * 0.015 * energy
    const targetRoot = (pose.lean || 0) * 0.18 + idleSway
    const alpha = 1 - Math.exp(-6 * delta)

    if (this.scene) {
      this.rootSway = MathUtils.lerp(this.rootSway, targetRoot, alpha)
      this.scene.rotation.z = MathUtils.lerp(this.scene.rotation.z, this.rootSway, alpha)
      this.scene.position.y = MathUtils.lerp(
        this.scene.position.y,
        this.basePositionY + Math.sin(elapsed * 1.6) * 0.008 * energy,
        alpha
      )
    }

    this.facial.update({
      delta,
      elapsed,
      pose,
      mouthAmplitude,
      isSpeaking: this.lipSync.speaking,
    })
    this.rig.update({
      delta,
      elapsed,
      action: this.resolvedAction?.action,
      pose,
      movement: this.resolvedAction?.movement,
      gesture: this.resolvedAction?.gesture,
      mouthAmplitude,
    })
  }

  dispose() {
    for (const action of Object.values(this.actions)) {
      try { action.stop() } catch {}
    }
    this.lipSync.dispose()
  }

  summary() {
    return {
      clips: this.registry.clipNames,
      activeClip: this.currentClip,
      fallbackClip: this.resolvedAction?.fallbackClip || false,
      facial: this.facial.summary(),
      rig: this.rig.summary(),
    }
  }
}

function getHoldPoseTime(duration = 0) {
  if (duration <= 0) return LACRIMOSA_IDLE_HOLD_SECONDS
  return Math.min(duration, LACRIMOSA_IDLE_HOLD_SECONDS)
}
