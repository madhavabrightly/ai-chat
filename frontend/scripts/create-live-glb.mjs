import { NodeIO } from '@gltf-transform/core'
import { ALL_EXTENSIONS } from '@gltf-transform/extensions'
import { dedup, prune } from '@gltf-transform/functions'
import { MeshoptDecoder, MeshoptEncoder } from 'meshoptimizer'

const [, , inputPath, outputPath] = process.argv

if (!inputPath || !outputPath) {
  console.error('Usage: node scripts/create-live-glb.mjs <input.glb> <output.glb>')
  process.exit(1)
}

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

// Preserve the original skeleton bind transforms. Sampling this source clip,
// even at frame zero, distorts its skinned geometry after morph targets go away.
removeAnimationPayload(root)

await document.transform(dedup(), prune())
await io.write(outputPath, document)

console.log(`Created live GLB: ${outputPath}`)

function removeAnimationPayload(root) {
  for (const animation of root.listAnimations()) {
    animation.dispose()
  }
}
