export default function StatusBadge({ online }) {
  return (
    <span className={`sb-badge ${online ? 'sb-live' : 'sb-off'}`}>
      <span className="sb-dot" />
      {online ? 'Live' : 'Offline'}
    </span>
  )
}
