import React, { Component, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { ContactShadows, OrbitControls, useAnimations, useGLTF } from '@react-three/drei'
import { Box3, Vector3 } from 'three'
import { clone } from 'three/examples/jsm/utils/SkeletonUtils.js'
import { AvatarController } from './AvatarController.js'
import { avatarEventBus } from './AvatarEventBus.js'

export const LACRIMOSA_MODEL_PATH = '/models/lacrimosa-live.glb'

class AvatarErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error) {
    this.props.onError?.(error)
  }

  render() {
    if (this.state.error) {
      return this.props.fallback
    }
    return this.props.children
  }
}

export function normalizeAvatarRoot(root) {
  if (!root || root.userData.memoryTwinNormalized) return null
  root.userData.memoryTwinNormalized = true
  root.traverse((object) => {
    if (object.isMesh || object.isSkinnedMesh) {
      object.frustumCulled = false
      object.castShadow = true
      object.receiveShadow = true
      if (object.material) {
        const materials = Array.isArray(object.material) ? object.material : [object.material]
        for (const material of materials) {
          material.needsUpdate = true
          if (/lacrimosa_01/i.test(material.name || '')) {
            object.visible = false
          }
        }
      }
    }
  })

  root.updateMatrixWorld(true)
  const sourceBox = new Box3().setFromObject(root)
  const sourceSize = sourceBox.getSize(new Vector3())
  if (!Number.isFinite(sourceSize.y) || sourceSize.y <= 0) {
    throw new Error('Lacrimosa model has no renderable bounds')
  }

  const targetHeight = 2.82
  const groundY = -1.46
  root.scale.multiplyScalar(targetHeight / sourceSize.y)
  root.updateMatrixWorld(true)

  const fittedBox = new Box3().setFromObject(root)
  const center = fittedBox.getCenter(new Vector3())
  root.position.x -= center.x
  root.position.y += groundY - fittedBox.min.y
  root.position.z -= center.z
  root.updateMatrixWorld(true)

  return {
    height: targetHeight,
    width: fittedBox.max.x - fittedBox.min.x,
  }
}

function AvatarModel({
  state,
  mood,
  isSpeaking,
  avatarPlan,
  onReady,
}) {
  const gltf = useGLTF(LACRIMOSA_MODEL_PATH, false, true)
  const avatarRoot = useMemo(() => clone(gltf.scene), [gltf.scene])
  const { actions } = useAnimations(gltf.animations, avatarRoot)
  const controllerRef = useRef(null)
  const reportedReadyRef = useRef(false)
  const actionKey = Object.keys(actions).join('|')

  useEffect(() => {
    normalizeAvatarRoot(avatarRoot)
  }, [avatarRoot])

  useEffect(() => {
    const controller = new AvatarController({
      scene: avatarRoot,
      actions,
      animations: gltf.animations || [],
    })
    controllerRef.current = controller
    controller.applyState({ state, mood, isSpeaking, plan: avatarPlan })
    reportedReadyRef.current = false
    return () => {
      controller.dispose()
      controllerRef.current = null
    }
  }, [avatarRoot, gltf.animations, actionKey])

  useEffect(() => {
    controllerRef.current?.applyState({ state, mood, isSpeaking, plan: avatarPlan })
    avatarEventBus.emit('avatar.state', { state, mood, isSpeaking, plan: avatarPlan || null })
  }, [state, mood, isSpeaking, avatarPlan])

  useFrame((frameState, delta) => {
    controllerRef.current?.update(delta, frameState.clock.elapsedTime)
    if (!reportedReadyRef.current && controllerRef.current) {
      reportedReadyRef.current = true
      const summary = controllerRef.current.summary()
      onReady?.(summary)
      avatarEventBus.emit('avatar.ready', summary)
    }
  })

  return <primitive object={avatarRoot} />
}

function AvatarFallback({ state, mood, reason = 'Loading GLB', hidden = false }) {
  return (
    <div className={`virtual-companion-fallback ${hidden ? 'is-hidden' : ''}`} aria-hidden={hidden}>
      <div className="vc-fallback-face">
        <span className="vc-fallback-eye" />
        <span className="vc-fallback-eye" />
        <span className="vc-fallback-mouth" />
      </div>
      <div className="vc-fallback-copy">
        <strong>Lacrimosa</strong>
        <span>{reason}</span>
        <small>{state || 'idle'} / {mood || 'calm'}</small>
      </div>
    </div>
  )
}

export default function VirtualCompanion({
  companion = 'female',
  state = 'idle',
  mood = 'calm',
  isSpeaking = false,
  avatarPlan = null,
  variant = 'panel',
}) {
  const [ready, setReady] = useState(false)
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState(null)

  const statusText = isSpeaking ? 'speaking' : state || 'idle'
  const clipLabel = summary?.activeClip
    ? summary.activeClip.split('|').pop()
    : 'live-pose'

  return (
    <div
      className={`avatar-stage virtual-companion-stage vc-${variant} vc-${statusText} vc-${mood} ${ready ? 'is-avatar-ready' : 'is-avatar-loading'}`}
      data-avatar-ready={ready ? 'true' : 'false'}
    >
      <AvatarErrorBoundary
        onError={(err) => {
          setError(err)
          setReady(false)
        }}
        fallback={<AvatarFallback state={state} mood={mood} reason="GLB asset unavailable" />}
      >
        <Suspense fallback={null}>
          <Canvas
            className="virtual-companion-canvas"
            camera={{ position: [0, 0.03, 5.2], fov: 37, near: 0.1, far: 50 }}
            dpr={[1, 1.35]}
            gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
          >
            <color attach="background" args={['#f6efe4']} />
            <ambientLight intensity={1.6} />
            <directionalLight position={[2.5, 3.5, 4]} intensity={2.2} />
            <directionalLight position={[-3, 2, -2]} intensity={0.8} color="#d9e8ff" />
            <group position={[0, 0, 0]}>
              <AvatarModel
                companion={companion}
                state={state}
                mood={mood}
                isSpeaking={isSpeaking}
                avatarPlan={avatarPlan}
                onReady={(nextSummary) => {
                  setSummary(nextSummary)
                  setReady(true)
                  setError(null)
                }}
              />
            </group>
            <ContactShadows position={[0, -1.47, 0]} opacity={0.2} scale={2.8} blur={2.4} far={2.2} />
            <OrbitControls
              enablePan={false}
              enableZoom={false}
              enableRotate={false}
              target={[0, 0.1, 0]}
            />
          </Canvas>
        </Suspense>
      </AvatarErrorBoundary>

      {!error && (
        <AvatarFallback state={state} mood={mood} reason="Preparing Lacrimosa" hidden={ready} />
      )}

      <div className="virtual-companion-glass">
        <div className={`vc-pulse ${isSpeaking ? 'is-speaking' : ''}`} />
        <span>{ready ? statusText : error ? 'offline' : 'loading'}</span>
        <small>{ready ? clipLabel : 'Three.js GLB'}</small>
      </div>
    </div>
  )
}

useGLTF.preload(LACRIMOSA_MODEL_PATH, false, true)
