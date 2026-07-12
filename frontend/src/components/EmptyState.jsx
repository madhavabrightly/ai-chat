export default function EmptyState({ icon, title, message }) {
  return (
    <div className="empty-state">
      {icon && <span className="empty-icon">{icon}</span>}
      {title && <h3 className="empty-title">{title}</h3>}
      {message && <p className="empty-msg">{message}</p>}
    </div>
  )
}
