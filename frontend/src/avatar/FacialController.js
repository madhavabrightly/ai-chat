import { MathUtils, Vector3 } from 'three'

function cloneEuler(euler) {
  return { x: euler.x, y: euler.y, z: euler.z }
}

function cloneVector(vector) {
  return new Vector3(vector.x, vector.y, vector.z)
}

function findObject(scene, tests) {
  let found = null
  scene.traverse((object) => {
    if (found) return
    const name = object.name || ''
    if (tests.some(test => test.test(name))) found = object
  })
  return found
}

function findObjects(scene, test, limit = 16) {
  const found = []
  scene.traverse((object) => {
    if (found.length >= limit) return
    if (test.test(object.name || '')) found.push(object)
  })
  return found
}

function collectMorphMeshes(scene) {
  const meshes = []
  scene.traverse((object) => {
    if (!object.morphTargetInfluences || !object.morphTargetDictionary) return
    const entries = Object.entries(object.morphTargetDictionary)
    const groups = {
      mouth: entries.filter(([name]) => /mouth|jaw|aa|oh|viseme|lip/i.test(name)).map(([, index]) => index),
      smile: entries.filter(([name]) => /smile|happy|joy|grin/i.test(name)).map(([, index]) => index),
      blink: entries.filter(([name]) => /blink|close|eyelid/i.test(name)).map(([, index]) => index),
      sad: entries.filter(([name]) => /sad|frown|angry/i.test(name)).map(([, index]) => index),
    }
    meshes.push({ object, groups })
  })
  return meshes
}

function applyMorph(meshes, group, value, alpha) {
  for (const mesh of meshes) {
    for (const index of mesh.groups[group] || []) {
      const current = mesh.object.morphTargetInfluences[index] || 0
      mesh.object.morphTargetInfluences[index] = MathUtils.lerp(current, value, alpha)
    }
  }
}

export class FacialController {
  constructor(scene) {
    this.scene = scene
    this.morphMeshes = collectMorphMeshes(scene)
    this.head = this.captureBone(findObject(scene, [/^Bone_head/i, /^Bip001-Head/i, /head/i]))
    this.neck = this.captureBone(findObject(scene, [/^Bip001-Neck/i, /neck/i]))
    this.mouth = this.captureBone(findObject(scene, [/^mouth/i, /jaw/i]))
    this.leftEye = this.captureBone(findObject(scene, [/^Bon_eyeball_L/i]))
    this.rightEye = this.captureBone(findObject(scene, [/^Bon_eyeball_R/i]))
    this.upperLids = findObjects(scene, /^BON_eyelid.*_up_[LR]/i, 12).map((bone) => this.captureBone(bone))
    this.lowerLids = findObjects(scene, /^BON_eyelid.*_lo_[LR]/i, 10).map((bone) => this.captureBone(bone))
    this.brows = findObjects(scene, /^Bon_eyebrow/i, 8).map((bone) => this.captureBone(bone))
    this.root = this.captureBone(findObject(scene, [/^Sketchfab_model/i]))
    this.expression = 'gentle_smile'
  }

  captureBone(object) {
    if (!object) return null
    return {
      object,
      rotation: cloneEuler(object.rotation),
      position: cloneVector(object.position),
    }
  }

  setExpression(expression) {
    this.expression = expression || 'gentle_smile'
  }

  setBone(handle, rotation, position, alpha) {
    if (!handle?.object) return
    const object = handle.object
    object.rotation.x = MathUtils.lerp(object.rotation.x, handle.rotation.x + (rotation.x || 0), alpha)
    object.rotation.y = MathUtils.lerp(object.rotation.y, handle.rotation.y + (rotation.y || 0), alpha)
    object.rotation.z = MathUtils.lerp(object.rotation.z, handle.rotation.z + (rotation.z || 0), alpha)
    if (position) {
      object.position.x = MathUtils.lerp(object.position.x, handle.position.x + (position.x || 0), alpha)
      object.position.y = MathUtils.lerp(object.position.y, handle.position.y + (position.y || 0), alpha)
      object.position.z = MathUtils.lerp(object.position.z, handle.position.z + (position.z || 0), alpha)
    }
  }

  update({ delta, elapsed, pose, mouthAmplitude, isSpeaking }) {
    const alpha = 1 - Math.exp(-10 * delta)
    const energy = pose?.energy || 0.2
    const focus = pose?.focus || 0.3
    const headYaw = (pose?.headYaw || 0) + Math.sin(elapsed * 0.72) * 0.025 * focus
    const headPitch = (pose?.headPitch || 0) + Math.sin(elapsed * 0.94) * 0.018 * energy
    const lean = (pose?.lean || 0) + Math.sin(elapsed * 0.52) * 0.012 * energy
    const blinkRate = Math.max(0.7, pose?.blinkRate || 1)
    const blinkPhase = (elapsed * blinkRate) % 4.7
    const primaryBlink = Math.exp(-Math.pow((blinkPhase - 0.12) / 0.065, 2))
    const doubleBlink = Math.exp(-Math.pow((blinkPhase - 0.34) / 0.075, 2)) * 0.22
    const blinkPulse = MathUtils.clamp(primaryBlink + doubleBlink, 0, 1)
    const smile = /smile|happy|grin|confident|warm/i.test(this.expression) ? 0.45 : 0.12
    const sad = /frown|tired|sad/i.test(this.expression) ? 0.34 : 0
    const mouth = MathUtils.clamp((mouthAmplitude || 0) + (pose?.mouthBoost || 0), 0, 1)

    this.setBone(this.head, {
      x: headPitch,
      y: headYaw,
      z: lean * 0.7,
    }, null, alpha)

    this.setBone(this.neck, {
      x: headPitch * 0.35,
      y: headYaw * 0.25,
      z: lean * 0.3,
    }, null, alpha)

    this.setBone(this.mouth, {
      x: mouth * 0.22,
      y: 0,
      z: 0,
    }, {
      x: 0,
      y: -mouth * 0.006,
      z: isSpeaking ? Math.sin(elapsed * 28) * 0.0015 : 0,
    }, alpha)

    const eyeYaw = Math.sin(elapsed * 0.36) * 0.025 + Math.sin(elapsed * 1.13) * 0.008
    const eyePitch = Math.sin(elapsed * 0.27 + 0.8) * 0.012 - headPitch * 0.08
    this.setBone(this.leftEye, { x: eyePitch, y: eyeYaw, z: 0 }, null, alpha * 0.75)
    this.setBone(this.rightEye, { x: eyePitch, y: eyeYaw, z: 0 }, null, alpha * 0.75)

    for (const lid of this.upperLids) {
      this.setBone(lid, { x: blinkPulse * 0.055, y: 0, z: 0 }, null, alpha)
    }
    for (const lid of this.lowerLids) {
      this.setBone(lid, { x: -blinkPulse * 0.028, y: 0, z: 0 }, null, alpha)
    }

    const browLift = /happy|smile|warm|confident|grin/i.test(this.expression) ? -0.014 : sad * 0.018
    this.brows.forEach((brow, index) => {
      const side = index % 2 === 0 ? 1 : -1
      this.setBone(brow, { x: browLift, y: 0, z: side * browLift * 0.18 }, null, alpha * 0.7)
    })

    applyMorph(this.morphMeshes, 'mouth', mouth, alpha)
    applyMorph(this.morphMeshes, 'smile', smile, alpha)
    applyMorph(this.morphMeshes, 'sad', sad, alpha)
    applyMorph(this.morphMeshes, 'blink', blinkPulse, alpha)
  }

  summary() {
    return {
      head: this.head?.object?.name || null,
      neck: this.neck?.object?.name || null,
      mouth: this.mouth?.object?.name || null,
      eyes: [this.leftEye?.object?.name, this.rightEye?.object?.name].filter(Boolean),
      eyelidBones: this.upperLids.length + this.lowerLids.length,
      morphMeshes: this.morphMeshes.length,
    }
  }
}
