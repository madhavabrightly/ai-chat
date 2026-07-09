const MALE_SVG = `<svg viewBox="0 0 80 100" xmlns="http://www.w3.org/2000/svg">
  <ellipse cx="40" cy="62" rx="14" ry="18" fill="#5a6b4a"/>
  <polygon points="36,48 40,56 44,48" fill="#4a5a3a"/>
  <rect x="35" y="44" width="10" height="14" rx="2" fill="#f5d6b8"/>
  <ellipse cx="40" cy="36" rx="13" ry="15" fill="#f5d6b8"/>
  <path d="M27,34 Q27,14 40,10 Q53,14 53,34 Q53,20 48,18 L44,10 Q40,7 36,10 L32,18 Q27,20 27,34 Z" fill="#4a3728"/>
  <path d="M28,32 Q40,24 52,32" fill="#5a4738" opacity="0.4"/>
  <circle cx="36" cy="33" r="2.8" fill="#3a281a"/>
  <circle cx="44" cy="33" r="2.8" fill="#3a281a"/>
  <circle cx="37" cy="31" r="1" fill="#fff" opacity="0.8"/>
  <circle cx="45" cy="31" r="1" fill="#fff" opacity="0.8"/>
  <line x1="33" y1="28" x2="37" y2="26" stroke="#3a281a" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="47" y1="28" x2="43" y2="26" stroke="#3a281a" stroke-width="1.5" stroke-linecap="round"/>
  <path d="M36,41 Q40,44 44,41" fill="none" stroke="#8b4040" stroke-width="1.8" stroke-linecap="round"/>
  <ellipse cx="100" cy="100" rx="25" ry="10" fill="rgba(0,0,0,0.08)"/>
</svg>`

const FEMALE_SVG = `<svg viewBox="0 0 80 100" xmlns="http://www.w3.org/2000/svg">
  <path d="M 30,50 Q 28,62 32,80 L 48,80 Q 52,62 50,50 Z" fill="#b8654a"/>
  <path d="M 34,50 L 46,50 Q 48,54 46,62 L 34,62 Q 32,54 34,50" fill="#c87050" opacity="0.5"/>
  <rect x="35" y="44" width="10" height="14" rx="2" fill="#f5d6b8"/>
  <ellipse cx="40" cy="36" rx="12" ry="14" fill="#f5d6b8"/>
  <path d="M24,36 Q24,10 40,6 Q56,10 56,36 Q56,18 50,14 L44,6 Q40,3 36,6 L30,14 Q24,18 24,36 Z" fill="#6b3a2a"/>
  <path d="M24,36 Q20,52 26,68" fill="none" stroke="#6b3a2a" stroke-width="4" stroke-linecap="round"/>
  <path d="M56,36 Q60,52 54,68" fill="none" stroke="#6b3a2a" stroke-width="4" stroke-linecap="round"/>
  <ellipse cx="28" cy="38" rx="6" ry="4" fill="#6b3a2a" opacity="0.5"/>
  <ellipse cx="52" cy="38" rx="6" ry="4" fill="#6b3a2a" opacity="0.5"/>
  <circle cx="36" cy="33" r="2.5" fill="#3a281a"/>
  <circle cx="44" cy="33" r="2.5" fill="#3a281a"/>
  <circle cx="37" cy="31" r="0.9" fill="#fff" opacity="0.8"/>
  <circle cx="45" cy="31" r="0.9" fill="#fff" opacity="0.8"/>
  <line x1="34" y1="28" x2="37" y2="26" stroke="#3a281a" stroke-width="1.2" stroke-linecap="round"/>
  <line x1="46" y1="28" x2="43" y2="26" stroke="#3a281a" stroke-width="1.2" stroke-linecap="round"/>
  <ellipse cx="33" cy="40" rx="4" ry="2" fill="#f0a0a0" opacity="0.25"/>
  <ellipse cx="47" cy="40" rx="4" ry="2" fill="#f0a0a0" opacity="0.25"/>
  <path d="M36,41 Q40,44 44,41" fill="none" stroke="#8b4040" stroke-width="1.8" stroke-linecap="round"/>
</svg>`

export default function CompanionSelector({ selected, onSelect }) {
  return (
    <div className="comp-sel">
      <div className="comp-sel-title">👤 Choose Companion</div>
      <div className="comp-sel-cards">
        <button className={`comp-card ${selected === 'male' ? 'comp-card-a' : ''}`} onClick={() => onSelect('male')}>
          <div className="comp-svg-wrap" dangerouslySetInnerHTML={{ __html: MALE_SVG }} />
          <div className="comp-name">Male Companion</div>
          <div className="comp-desc">Warm, calm, thoughtful</div>
        </button>
        <button className={`comp-card ${selected === 'female' ? 'comp-card-a' : ''}`} onClick={() => onSelect('female')}>
          <div className="comp-svg-wrap" dangerouslySetInnerHTML={{ __html: FEMALE_SVG }} />
          <div className="comp-name">Female Companion</div>
          <div className="comp-desc">Gentle, kind, warm-hearted</div>
        </button>
      </div>
      {selected && (
        <button className="btn-ghost-xs" style={{ width: '100%', marginTop: 8 }} onClick={() => { localStorage.removeItem('mt_companion'); onSelect(null) }}>
          Change Companion
        </button>
      )}
    </div>
  )
}
