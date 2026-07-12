export default function GlowingOrb({ pulsing = false, size = 100 }) {
  return (
    <div className={`orb-wrap${pulsing ? ' orb-pulse' : ''}`} style={{ width: size, height: size }}>
      <div className="orb-circle" style={{ width: size, height: size }}>
        <div className="orb-inner" style={{ width: size * 0.48, height: size * 0.48 }} />
      </div>
    </div>
  )
}
