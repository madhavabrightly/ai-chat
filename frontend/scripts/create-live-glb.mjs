import { NodeIO } from '@gltf-transform/core'
import { ALL_EXTENSIONS } from '@gltf-transform/extensions'
import { dedup, prune } from '@gltf-transform/functions'
import { MeshoptDecoder, MeshoptEncoder } from 'meshoptimizer'
import { Quaternion } from 'three'

const [, , inputPath, outputPath] = process.argv

if (!inputPath || !outputPath) {
  console.error('Usage: node scripts/create-live-glb.mjs <input.glb> <output.glb>')
  process.exit(1)
}

const HOLD_POSE_SECONDS = 0
const HIDDEN_MATERIAL = /lacrimosa_01/i

await MeshoptDecoder.ready
await MeshoptEncoder.ready

const io = new NodeIO()
  .registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({
    'meshopt.decoder': MeshoptDecoder,
    'meshopt.encoder': MeshoptEncoder,
  })

const document = await io.read(inputPath)
const root = document.getRoot()

// Preserve original bind transforms; do not sample source animation.
removeAnimationPayload(root)

await document.transform(dedup(), prune())
await io.write(outputPath, document)

console.log(`Created live GLB: ${outputPath}`)

function bakeAnimationPose(root, timeSeconds) {
  for (const animation of root.listAnimations()) {
    for (const channel of animation.listChannels()) {
      const targetNode = channel.getTargetNode()
      const targetPath = channel.getTargetPath()
      const sampler = channel.getSampler()
      if (!targetNode || !sampler) continue

      const value = sampleChannel(sampler, targetPath, timeSeconds)
      if (!value) continue

      if (targetPath === 'translation') targetNode.setTranslation(value)
      if (targetPath === 'rotation') targetNode.setRotation(value)
      if (targetPath === 'scale') targetNode.setScale(value)
      if (targetPath === 'weights') targetNode.setWeights(value)
    }
  }
}

function sampleChannel(sampler, targetPath, timeSeconds) {
  const input = sampler.getInput()
  const output = sampler.getOutput()
  if (!input || !output) return null

  const times = input.getArray()
  if (!times?.length) return null

  const interpolation = sampler.getInterpolation()
  let left = 0
  while (left < times.length - 1 && times[left + 1] <= timeSeconds) left += 1
  const right = Math.min(left + 1, times.length - 1)

  const readIndex = (index) => {
    const offset = interpolation === 'CUBICSPLINE' ? index * 3 + 1 : index
    const value = []
    output.getElement(offset, value)
    return value
  }

  const leftValue = readIndex(left)
  if (right === left || interpolation === 'STEP' || interpolation === 'CUBICSPLINE') {
    return leftValue
  }

  const rightValue = readIndex(right)
  const span = times[right] - times[left]
  const alpha = span > 0 ? (timeSeconds - times[left]) / span : 0

  if (targetPath === 'rotation') {
    const leftQuat = new Quaternion(...leftValue)
    const rightQuat = new Quaternion(...rightValue)
    return leftQuat.slerp(rightQuat, alpha).toArray()
  }

  return leftValue.map((value, index) => value + (rightValue[index] - value) * alpha)
}

function removeAnimationPayload(root) {
  for (const animation of root.listAnimations()) {
    animation.dispose()
  }
}

