import { MathUtils } from 'three'

const BODY_BONES = {
  spineLower: [/^Bip001-Spine_/, /^Bip001-Spine$/i],
  spineMid: [/^Bip001-Spine1_/, /^Bip001-Spine1$/i],
  spineUpper: [/^Bip001-Spine2_/, /^Bip001-Spine2$/i],
  pelvis: [/^Bip001-Pelvis_/, /^Bip001-Pelvis$/i],
  leftClavicle: [/^Bip001-L-Clavicle_/, /^Bip001-L-Clavicle$/i],
  rightClavicle: [/^Bip001-R-Clavicle_/, /^Bip001-R-Clavicle$/i],
  leftUpperArm: [/^Bip001-L-UpperArm_/, /^Bip001-L-UpperArm$/i],
  rightUpperArm: [/^Bip001-R-UpperArm_/, /^Bip001-R-UpperArm$/i],
  leftForearm: [/^Bip001-L-Forearm_/, /^Bip001-L-Forearm$/i],
  rightForearm: [/^Bip001-R-Forearm_/, /^Bip001-R-Forearm$/i],
  leftHand: [/^Bip001-L-Hand_/, /^Bip001-L-Hand$/i],
  rightHand: [/^Bip001-R-Hand_/, /^Bip001-R-Hand$/i],
}

const MOTION_PRESETS = {
  idle: { lean: 0, turn: 0, lift: 0, openness: 0, tempo: 0.7 },
  listening: { lean: 0.018, turn: -0.018, lift: 0.006, openness: 0.012, tempo: 0.8 },
  thinking: { lean: -0.012, turn: 0.035, lift: -0.006, openness: -0.012, tempo: 0.55 },
  speaking: { lean: 0.022, turn: 0.012, lift: 0.012, openness: 0.026, tempo: 1.35 },
  happy: { lean: 0.018, turn: -0.012, lift: 0.018, openness: 0.038, tempo: 1.2 },
  funny: { lean: 0.035, turn: 0.035, lift: 0.02, openness: 0.045, tempo: 1.45 },
  proud: { lean: -0.018, turn: -0.01, lift: 0.026, openness: 0.03, tempo: 0.9 },
  thoughtful: { lean: -0.01, turn: 0.03, lift: -0.004, openness: -0.01, tempo: 0.6 },
  kind: { lean: 0.024, turn: -0.018, lift: 0.008, openness: 0.022, tempo: 0.75 },
  bored: { lean: -0.025, turn: 0.016, lift: -0.022, openness: -0.02, tempo: 0.45 },
  error: { lean: -0.012, turn: 0.025, lift: -0.012, openness: -0.012, tempo: 0.55 },
}

function findObject(scene, tests) {
  let found = null
  scene?.traverse((object) => {
    if (found) return
    const name = object.name || ''
    if (tests.some((test) => test.test(name))) found = object
  })
  return found
}

function captureBone(object) {
  if (!object) return null
  return {
    object,
    rotation: {
      x: object.rotation.x,
      y: object.rotation.y,
      z: object.rotation.z,
    },
  }
}

function applyRotation(handle, offset, alpha) {
  if (!handle?.object) return
  const { object, rotation } = handle
  object.rotation.x = MathUtils.lerp(object.rotation.x, rotation.x + (offset.x || 0), alpha)
  object.rotation.y = MathUtils.lerp(object.rotation.y, rotation.y + (offset.y || 0), alpha)
  object.rotation.z = MathUtils.lerp(object.rotation.z, rotation.z + (offset.z || 0), alpha)
}

function collectSecondaryBones(scene) {
  const handles = []
  scene?.traverse((object) => {
    const name = object.name || ''
    if (!object.isBone) return
    if (!/Bn_[lrm]_(hair|tail|piaodai|tie)/i.test(name)) return
    if (handles.length >= 36) return
    handles.push(captureBone(object))
  })
  return handles.filter(Boolean)
}

export class ProceduralRigController {
  constructor(scene) {
    this.bones = Object.fromEntries(
      Object.entries(BODY_BONES).map(([key, tests]) => [key, captureBone(findObject(scene, tests))])
    )
    this.secondary = collectSecondaryBones(scene)
  }

  update({ delta, elapsed, action = 'idle', pose = {}, movement = '', gesture = '', mouthAmplitude = 0 }) {
    const preset = MOTION_PRESETS[action] || MOTION_PRESETS.idle
    const energy = MathUtils.clamp(pose.energy || 0.24, 0.08, 1)
    const tempo = preset.tempo * (0.82 + energy * 0.34)
    const breath = Math.sin(elapsed * tempo * 1.6)
    const conversationalBeat = Math.sin(elapsed * 3.1) * mouthAmplitude
    const alpha = 1 - Math.exp(-7.5 * delta)

    const planLean = /lean_forward|lean_in/i.test(movement) ? 0.018 : 0
    const planLift = /stand_tall|hands_chest|hand_heart/i.test(`${movement} ${gesture}`) ? 0.014 : 0
    const planOpen = /hands_open|hand_wave/i.test(gesture) ? 0.02 : 0
    const torsoLean = preset.lean + planLean + breath * 0.006 * energy
    const torsoTurn = preset.turn + Math.sin(elapsed * 0.42) * 0.007 * energy
    const shoulderLift = preset.lift + planLift + breath * 0.004 * energy
    const armOpen = preset.openness + planOpen + conversationalBeat * 0.008

    applyRotation(this.bones.pelvis, { x: -torsoLean * 0.2, y: -torsoTurn * 0.12, z: 0 }, alpha)
    applyRotation(this.bones.spineLower, { x: torsoLean * 0.22, y: torsoTurn * 0.2, z: 0 }, alpha)
    applyRotation(this.bones.spineMid, { x: torsoLean * 0.38, y: torsoTurn * 0.34, z: -torsoTurn * 0.08 }, alpha)
    applyRotation(this.bones.spineUpper, { x: torsoLean * 0.52, y: torsoTurn * 0.46, z: -torsoTurn * 0.12 }, alpha)

    applyRotation(this.bones.leftClavicle, { x: 0, y: 0, z: shoulderLift + armOpen * 0.18 }, alpha)
    applyRotation(this.bones.rightClavicle, { x: 0, y: 0, z: -shoulderLift - armOpen * 0.18 }, alpha)
    applyRotation(this.bones.leftUpperArm, { x: conversationalBeat * 0.01, y: armOpen * 0.24, z: armOpen * 0.42 }, alpha)
    applyRotation(this.bones.rightUpperArm, { x: -conversationalBeat * 0.01, y: -armOpen * 0.24, z: -armOpen * 0.42 }, alpha)
    applyRotation(this.bones.leftForearm, { x: mouthAmplitude * 0.008, y: 0, z: conversationalBeat * 0.008 }, alpha)
    applyRotation(this.bones.rightForearm, { x: -mouthAmplitude * 0.008, y: 0, z: -conversationalBeat * 0.008 }, alpha)
    applyRotation(this.bones.leftHand, { x: 0, y: conversationalBeat * 0.006, z: breath * 0.004 }, alpha)
    applyRotation(this.bones.rightHand, { x: 0, y: -conversationalBeat * 0.006, z: -breath * 0.004 }, alpha)

    this.secondary.forEach((handle, index) => {
      const phase = elapsed * (0.48 + (index % 5) * 0.035) + index * 0.63
      const sway = Math.sin(phase) * 0.0045 * energy
      applyRotation(handle, { x: sway * 0.4, y: sway, z: sway * 0.65 }, alpha * 0.7)
    })
  }

  summary() {
    return {
      bodyBones: Object.values(this.bones).filter(Boolean).length,
      secondaryBones: this.secondary.length,
      mode: 'procedural-rig',
    }
  }
}
