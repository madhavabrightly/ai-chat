import { copyFileSync, existsSync, mkdirSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { dirname } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const root = join(here, '..')
const publicVad = join(root, 'public', 'vad-assets')
const publicOnnx = join(publicVad, 'onnx')
const vadDist = join(root, 'node_modules', '@ricky0123', 'vad-web', 'dist')
const ortDist = join(root, 'node_modules', 'onnxruntime-web', 'dist')

if (!existsSync(vadDist) || !existsSync(ortDist)) {
  console.log('[sync-vad-assets] node_modules not ready; skipping')
  process.exit(0)
}

mkdirSync(publicVad, { recursive: true })
mkdirSync(publicOnnx, { recursive: true })

for (const name of ['silero_vad_legacy.onnx', 'silero_vad_v5.onnx', 'vad.worklet.bundle.min.js']) {
  copyFileSync(join(vadDist, name), join(publicVad, name))
}

for (const name of readdirSync(ortDist)) {
  if (name.startsWith('ort-wasm-simd-threaded')) {
    copyFileSync(join(ortDist, name), join(publicOnnx, name))
  }
}

console.log('[sync-vad-assets] VAD assets ready')
