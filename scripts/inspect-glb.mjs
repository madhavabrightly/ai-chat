import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const defaultInput = path.join(repoRoot, 'frontend', 'public', 'models', 'lacrimosa.glb')
const defaultOutput = path.join(repoRoot, 'reports', 'lacrimosa-glb-report.json')

const inputPath = path.resolve(process.argv[2] || defaultInput)
const outputPath = path.resolve(process.argv[3] || defaultOutput)

const GLB_MAGIC = 0x46546c67
const GLB_JSON = 0x4e4f534a
const GLB_BIN = 0x004e4942

function readGlb(filePath) {
  const buffer = fs.readFileSync(filePath)
  if (buffer.readUInt32LE(0) !== GLB_MAGIC) {
    throw new Error(`${filePath} is not a GLB file`)
  }

  const version = buffer.readUInt32LE(4)
  const declaredLength = buffer.readUInt32LE(8)
  let offset = 12
  let json = null
  let binaryChunk = null
  const chunks = []

  while (offset + 8 <= buffer.length) {
    const chunkLength = buffer.readUInt32LE(offset)
    const chunkType = buffer.readUInt32LE(offset + 4)
    const chunkStart = offset + 8
    const chunkEnd = chunkStart + chunkLength
    const chunk = buffer.subarray(chunkStart, chunkEnd)
    chunks.push({ type: chunkType, length: chunkLength })
    if (chunkType === GLB_JSON) {
      json = JSON.parse(chunk.toString('utf8').trim())
    } else if (chunkType === GLB_BIN) {
      binaryChunk = chunk
    }
    offset = chunkEnd
  }

  if (!json) throw new Error('GLB did not contain a JSON chunk')
  return { buffer, version, declaredLength, json, binaryChunk, chunks }
}

function nodeName(json, index) {
  if (index === undefined || index === null) return null
  return json.nodes?.[index]?.name || `node_${index}`
}

function accessor(json, index) {
  return index === undefined || index === null ? null : json.accessors?.[index] || null
}

function animationDuration(json, animation) {
  let duration = 0
  for (const sampler of animation.samplers || []) {
    const inputAccessor = accessor(json, sampler.input)
    if (Array.isArray(inputAccessor?.max) && Number.isFinite(inputAccessor.max[0])) {
      duration = Math.max(duration, inputAccessor.max[0])
    }
  }
  return duration
}

function triangleCountForPrimitive(json, primitive) {
  const mode = primitive.mode ?? 4
  const indexed = accessor(json, primitive.indices)
  const positions = accessor(json, primitive.attributes?.POSITION)
  const count = indexed?.count || positions?.count || 0
  if (mode === 4) return Math.floor(count / 3)
  if (mode === 5 || mode === 6) return Math.max(0, count - 2)
  return 0
}

function readPngDimensions(buffer) {
  if (!buffer || buffer.length < 24) return null
  const signature = buffer.subarray(0, 8).toString('hex')
  if (signature !== '89504e470d0a1a0a') return null
  return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) }
}

function readJpegDimensions(buffer) {
  if (!buffer || buffer.length < 4 || buffer[0] !== 0xff || buffer[1] !== 0xd8) return null
  let offset = 2
  while (offset + 9 < buffer.length) {
    if (buffer[offset] !== 0xff) {
      offset += 1
      continue
    }
    const marker = buffer[offset + 1]
    const length = buffer.readUInt16BE(offset + 2)
    if (length < 2) return null
    const isStartOfFrame = marker >= 0xc0 && marker <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marker)
    if (isStartOfFrame) {
      return {
        width: buffer.readUInt16BE(offset + 7),
        height: buffer.readUInt16BE(offset + 5),
      }
    }
    offset += 2 + length
  }
  return null
}

function imageDimensions(json, binaryChunk, image) {
  if (!image) return null
  if (image.uri) return { source: 'external', uri: image.uri }
  const view = json.bufferViews?.[image.bufferView]
  if (!view || !binaryChunk) return null
  const byteOffset = view.byteOffset || 0
  const bytes = binaryChunk.subarray(byteOffset, byteOffset + view.byteLength)
  return readPngDimensions(bytes) || readJpegDimensions(bytes) || null
}

function unique(values) {
  return [...new Set(values.filter(Boolean))]
}

function buildReport(filePath, parsed) {
  const { json, binaryChunk, version, declaredLength, chunks } = parsed
  const meshSummaries = (json.meshes || []).map((mesh, meshIndex) => {
    const primitives = mesh.primitives || []
    const primitiveReports = primitives.map((primitive, primitiveIndex) => ({
      primitiveIndex,
      mode: primitive.mode ?? 4,
      material: primitive.material ?? null,
      triangles: triangleCountForPrimitive(json, primitive),
      attributes: Object.keys(primitive.attributes || {}),
      morphTargetCount: primitive.targets?.length || 0,
    }))

    const fallbackTargetCount = Math.max(0, ...primitiveReports.map(p => p.morphTargetCount))
    const targetNames = fallbackTargetCount > 0 && Array.isArray(mesh.extras?.targetNames)
      ? mesh.extras.targetNames
      : []
    const morphTargets = targetNames.length
      ? targetNames
      : Array.from({ length: fallbackTargetCount }, (_, i) => `morph_${i}`)

    return {
      index: meshIndex,
      name: mesh.name || `mesh_${meshIndex}`,
      primitives: primitiveReports,
      triangleCount: primitiveReports.reduce((sum, p) => sum + p.triangles, 0),
      morphTargets,
    }
  })

  const animations = (json.animations || []).map((animation, index) => ({
    index,
    name: animation.name || `Animation ${index + 1}`,
    durationSeconds: Number(animationDuration(json, animation).toFixed(3)),
    samplerCount: animation.samplers?.length || 0,
    channels: (animation.channels || []).map(channel => ({
      node: nodeName(json, channel.target?.node),
      path: channel.target?.path || 'unknown',
    })),
  }))

  const skins = (json.skins || []).map((skin, index) => ({
    index,
    name: skin.name || `skin_${index}`,
    skeleton: nodeName(json, skin.skeleton),
    jointCount: skin.joints?.length || 0,
    joints: (skin.joints || []).map(joint => nodeName(json, joint)),
  }))

  const allJointNames = unique(skins.flatMap(skin => skin.joints))
  const candidateBones = {
    head: allJointNames.filter(name => /head/i.test(name)),
    neck: allJointNames.filter(name => /neck/i.test(name)),
    jaw: allJointNames.filter(name => /jaw|mouth|chin/i.test(name)),
    eyes: allJointNames.filter(name => /eye|eyelid|blink/i.test(name)),
    hands: allJointNames.filter(name => /hand|finger|wrist/i.test(name)),
  }

  const images = (json.images || []).map((image, index) => ({
    index,
    name: image.name || `image_${index}`,
    mimeType: image.mimeType || null,
    bufferView: image.bufferView ?? null,
    dimensions: imageDimensions(json, binaryChunk, image),
  }))

  const morphTargets = unique(meshSummaries.flatMap(mesh => mesh.morphTargets))

  return {
    inspectedAt: new Date().toISOString(),
    file: {
      path: filePath,
      sizeBytes: fs.statSync(filePath).size,
    },
    glb: {
      version,
      declaredLength,
      chunks: chunks.map(chunk => ({
        type: chunk.type === GLB_JSON ? 'JSON' : chunk.type === GLB_BIN ? 'BIN' : String(chunk.type),
        length: chunk.length,
      })),
    },
    asset: json.asset || {},
    counts: {
      scenes: json.scenes?.length || 0,
      nodes: json.nodes?.length || 0,
      meshes: json.meshes?.length || 0,
      materials: json.materials?.length || 0,
      textures: json.textures?.length || 0,
      images: json.images?.length || 0,
      skins: json.skins?.length || 0,
      animations: json.animations?.length || 0,
      morphTargets: morphTargets.length,
      triangles: meshSummaries.reduce((sum, mesh) => sum + mesh.triangleCount, 0),
    },
    scenes: (json.scenes || []).map((scene, index) => ({
      index,
      name: scene.name || `scene_${index}`,
      nodes: (scene.nodes || []).map(node => nodeName(json, node)),
    })),
    meshes: meshSummaries,
    materials: (json.materials || []).map((material, index) => ({
      index,
      name: material.name || `material_${index}`,
      alphaMode: material.alphaMode || 'OPAQUE',
      doubleSided: Boolean(material.doubleSided),
      extensions: Object.keys(material.extensions || {}),
    })),
    images,
    skins,
    bones: {
      count: allJointNames.length,
      all: allJointNames,
      candidates: candidateBones,
    },
    morphTargets,
    animations,
    extensionsUsed: json.extensionsUsed || [],
    extensionsRequired: json.extensionsRequired || [],
  }
}

const parsed = readGlb(inputPath)
const report = buildReport(inputPath, parsed)
fs.mkdirSync(path.dirname(outputPath), { recursive: true })
fs.writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`)

console.log(`Inspected ${path.basename(inputPath)}`)
console.log(`Animations: ${report.animations.map(a => a.name).join(', ') || 'none'}`)
console.log(`Bones: ${report.bones.count}, morph targets: ${report.morphTargets.length}, triangles: ${report.counts.triangles}`)
console.log(`Report: ${outputPath}`)
