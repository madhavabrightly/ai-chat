import { useEffect, useState } from 'react'

const MOOD_LABELS = {
  calm: '😊', happy: '😄', thoughtful: '🤔', funny: '😆',
  kind: '🥰', proud: '😌', bored: '🥱',
}

export default function AnimeAvatarStage({ companion, state, mood, isSpeaking }) {
  const [phase, setPhase] = useState(0)
  const [mouthIdx, setMouthIdx] = useState(0)
  const [blink, setBlink] = useState(false)

  useEffect(() => {
    if (!companion) return
    setPhase(0)
    const t1 = setTimeout(() => setPhase(1), 400)
    const t2 = setTimeout(() => setPhase(2), 1800)
    return () => { clearTimeout(t1); clearTimeout(t2) }
  }, [companion])

  useEffect(() => {
    const interval = setInterval(() => {
      setBlink(true)
      setTimeout(() => setBlink(false), 150)
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (!isSpeaking) { setMouthIdx(0); return }
    const interval = setInterval(() => setMouthIdx(prev => (prev + 1) % 3), 120)
    return () => clearInterval(interval)
  }, [isSpeaking])

  if (!companion) return null

  const isFemale = companion === 'female'
  const moodEmoji = MOOD_LABELS[mood] || '😊'
  const skin = '#f5d6b8'
  const mHair = '#4a3728'
  const fHair = '#6b3a2a'
  const mShirt = '#5a6b4a'
  const fDress = '#b8654a'
  const eyeColor = '#3a281a'

  const mouths = [
    'M 45,115 Q 50,110 55,115',
    'M 44,118 Q 50,112 56,118',
    'M 43,123 Q 50,113 57,123',
  ]

  const isBlink = blink
  const eyeY = state === 'thinking' ? 78 : 80
  const pupilY = state === 'thinking' ? 76 : 80
  const headTilt = state === 'thinking' ? -6 : state === 'funny' ? 10 : state === 'listening' ? 4 : 0
  const bodySway = state === 'thinking' ? -3 : state === 'funny' ? 5 : 0

  // Eyebrow angles per mood
  const ebL = mood === 'thoughtful' ? 12 : mood === 'proud' ? -10 : mood === 'funny' ? -8 : 0
  const ebR = mood === 'thoughtful' ? 12 : mood === 'proud' ? -10 : mood === 'funny' ? 8 : 0

  const showSparkles = mood === 'happy' || mood === 'proud'
  const showBlush = mood === 'happy' || mood === 'funny' || mood === 'kind'

  return (
    <div className="avatar-stage">
      <svg viewBox="0 0 280 280" className="avatar-svg">
        {/* Warm wall */}
        <rect x="0" y="0" width="280" height="200" fill="#f0e0c8" />
        <rect x="0" y="200" width="280" height="80" fill="#c4a87c" />
        <line x1="0" y1="218" x2="280" y2="218" stroke="#b8946a" strokeWidth="1" />
        <line x1="0" y1="236" x2="280" y2="236" stroke="#b8946a" strokeWidth="1" />
        <line x1="0" y1="254" x2="280" y2="254" stroke="#b8946a" strokeWidth="1" />

        {/* Window with warm light */}
        <rect x="20" y="35" width="56" height="72" rx="3" fill="#b8d8ea" stroke="#7a5a10" strokeWidth="3" />
        <line x1="48" y1="35" x2="48" y2="107" stroke="#7a5a10" strokeWidth="2" />
        <line x1="20" y1="71" x2="76" y2="71" stroke="#7a5a10" strokeWidth="2" />
        <rect x="24" y="39" width="20" height="28" rx="1" fill="#c8e8f0" opacity="0.7" />

        {/* Lamp glow */}
        <rect x="220" y="12" width="4" height="22" fill="#8b6914" />
        <ellipse cx="222" cy="36" rx="16" ry="10" fill="#f5e6a0" opacity="0.5" />
        <ellipse cx="222" cy="38" rx="10" ry="5" fill="#ffd700" opacity="0.15" />

        {/* Picture frame on wall */}
        <rect x="140" y="25" width="30" height="35" rx="2" fill="#c9a96e" stroke="#7a5a10" strokeWidth="2" />
        <circle cx="155" cy="38" r="4" fill="#a0806a" />
        <rect x="143" y="44" width="24" height="12" rx="1" fill="#a0806a" opacity="0.5" />

        {/* Door */}
        <g className={`svg-door ${phase >= 1 ? 'svg-door-open' : ''}`}>
          <rect x="210" y="118" width="46" height="82" rx="2" fill="#8b6914" stroke="#5a3a00" strokeWidth="2" />
          <rect x="214" y="122" width="38" height="74" fill="#9a7a20" />
          <circle cx="245" cy="161" r="3" fill="#c9a96e" />
          <rect x="222" y="128" width="12" height="18" rx="1" fill="#b8946a" opacity="0.6" />
          <rect x="225" y="160" width="14" height="20" rx="1" fill="#b8946a" opacity="0.4" />
        </g>
        {phase === 1 && <rect x="205" y="116" width="60" height="88" fill="#fff8e0" opacity="0.25" rx="2" />}

        {/* Character */}
        {phase >= 2 && (
          <g transform={`translate(${bodySway}, 0)`} className="svg-char">
            <g transform={`rotate(${headTilt}, 100, 100)`}>
              {/* Shadow */}
              <ellipse cx="100" cy="200" rx="24" ry="6" fill="rgba(0,0,0,0.1)" />

              {/* Body / Outfit */}
              {isFemale ? (
                <>
                  <path d="M 82,150 Q 80,175 80,198 L 120,198 Q 120,175 118,150 Z" fill={fDress} />
                  <path d="M 86,150 L 114,150 Q 118,155 114,165 L 86,165 Q 82,155 86,150" fill="#c87050" opacity="0.5" />
                  <path d="M 82,150 Q 76,160 72,175 Q 74,178 77,175 Q 78,165 82,155" fill={skin} />
                  <path d="M 118,150 Q 124,160 128,175 Q 126,178 123,175 Q 122,165 118,155" fill={skin} />
                </>
              ) : (
                <>
                  <rect x="82" y="148" width="36" height="50" rx="4" fill={mShirt} />
                  <polygon points="90,148 100,160 110,148" fill="#4a5a3a" />
                  <rect x="76" y="152" width="7" height="35" rx="3" fill={skin} />
                  <rect x="117" y="152" width="7" height="35" rx="3" fill={skin} />
                </>
              )}

              {/* Neck */}
              <rect x="94" y="120" width="12" height="30" fill={skin} rx="2" />

              {/* Head */}
              <ellipse cx="100" cy="90" rx="30" ry="34" fill={skin} />

              {/* Male Hair — styled anime cut */}
              {!isFemale && (
                <>
                  <path d="M 70,85 Q 68,55 82,42 Q 95,32 105,32 Q 118,36 128,50 Q 132,60 130,80 Q 128,68 120,60 L 112,48 Q 105,40 95,40 Q 85,42 78,52 L 72,65 Q 68,72 70,85 Z" fill={mHair} />
                  <path d="M 72,82 L 128,82 Q 130,74 128,68" fill={mHair} />
                  <path d="M 78,50 Q 85,38 100,35 Q 115,38 122,50" fill="#5a4738" opacity="0.4" />
                </>
              )}

              {/* Female Hair — longer flowing */}
              {isFemale && (
                <>
                  <path d="M 66,90 Q 62,50 80,38 Q 95,30 110,32 Q 128,40 134,70 Q 136,85 134,95 Q 130,80 124,68 L 112,48 Q 100,38 88,42 L 76,55 Q 68,68 66,90 Z" fill={fHair} />
                  <path d="M 66,90 Q 60,115 64,145 Q 62,150 66,148 Q 68,130 68,110" fill={fHair} />
                  <path d="M 134,95 Q 140,120 136,148 Q 138,150 134,148 Q 132,125 132,105" fill={fHair} />
                  <path d="M 68,90 Q 64,110 66,130" fill="none" stroke={fHair} strokeWidth="4" strokeLinecap="round" />
                  <path d="M 132,90 Q 136,110 134,130" fill="none" stroke={fHair} strokeWidth="4" strokeLinecap="round" />
                  <ellipse cx="70" cy="88" rx="8" ry="6" fill={fHair} opacity="0.6" />
                  <ellipse cx="130" cy="88" rx="8" ry="6" fill={fHair} opacity="0.6" />
                </>
              )}

              {/* Eyebrows */}
              <line x1="80" y1="72" x2="91" y2={68 + ebL} stroke="#3a281a" strokeWidth="2.2" strokeLinecap="round" />
              <line x1="109" y1={68 + ebR} x2="120" y2="72" stroke="#3a281a" strokeWidth="2.2" strokeLinecap="round" />

              {/* Eyes */}
              <ellipse cx="88" cy={eyeY} rx="5.5" ry={isBlink ? 0.5 : 5} fill={eyeColor} />
              <ellipse cx="112" cy={eyeY} rx="5.5" ry={isBlink ? 0.5 : 5} fill={eyeColor} />
              {isBlink || (
                <>
                  <circle cx="89" cy={pupilY - 1} r="2" fill="#fff" />
                  <circle cx="113" cy={pupilY - 1} r="2" fill="#fff" />
                  <circle cx="87" cy={pupilY - 3} r="0.8" fill="#fff" opacity="0.5" />
                  <circle cx="111" cy={pupilY - 3} r="0.8" fill="#fff" opacity="0.5" />
                </>
              )}

              {/* Blush */}
              {showBlush && (
                <>
                  <ellipse cx="79" cy="97" rx="7" ry="3.5" fill="#f0a0a0" opacity="0.35" />
                  <ellipse cx="121" cy="97" rx="7" ry="3.5" fill="#f0a0a0" opacity="0.35" />
                </>
              )}

              {/* Nose */}
              <path d="M 99,88 Q 100,93 101,88" fill="none" stroke="#d4a080" strokeWidth="1.2" strokeLinecap="round" />

              {/* Mouth */}
              {mood === 'happy' || mood === 'proud' ? (
                <path d="M 44,116 Q 50,108 56,116" fill="none" stroke="#8b4040" strokeWidth="2.5" strokeLinecap="round" />
              ) : mood === 'thoughtful' || mood === 'bored' ? (
                <ellipse cx="50" cy="118" rx="4" ry="3" fill="none" stroke="#8b4040" strokeWidth="1.8" />
              ) : mood === 'funny' ? (
                <path d="M 43,118 Q 50,106 57,118" fill="none" stroke="#8b4040" strokeWidth="2.5" strokeLinecap="round" />
              ) : (
                <path d={mouths[mouthIdx]} fill="none" stroke="#8b4040" strokeWidth="2.5" strokeLinecap="round" />
              )}

              {/* Thinking particles */}
              {state === 'thinking' && (
                <>
                  <circle cx="138" cy="42" r="4" fill="#c9a96e" opacity="0.6" className="think-dot" />
                  <circle cx="145" cy="30" r="3" fill="#c9a96e" opacity="0.4" className="think-dot" style={{ animationDelay: '0.2s' }} />
                  <circle cx="150" cy="20" r="5" fill="#c9a96e" opacity="0.3" className="think-dot" style={{ animationDelay: '0.4s' }} />
                </>
              )}

              {/* Sparkles */}
              {showSparkles && (
                <>
                  <text x="132" y="52" fontSize="14" opacity="0.5" className="sparkle-text">✦</text>
                  <text x="58" y="45" fontSize="10" opacity="0.35" className="sparkle-text" style={{ animationDelay: '0.5s' }}>✦</text>
                  <text x="140" y="65" fontSize="8" opacity="0.3" className="sparkle-text" style={{ animationDelay: '1s' }}>✦</text>
                </>
              )}
            </g>
          </g>
        )}
      </svg>

      {/* State label */}
      {state && state !== 'idle' && (
        <div className="avatar-state-label">
          {state === 'listening' && '👂 Listening...'}
          {state === 'thinking' && '🤔 Searching memories...'}
          {state === 'speaking' && '💬 Speaking...'}
          {state === 'greeting' && 'Hello! 👋'}
          {(state === 'happy' || state === 'proud') && `😊 Feeling ${state}`}
          {state === 'thoughtful' && '🤔 Reflecting...'}
          {state === 'funny' && '😆 That\'s funny!'}
          {state === 'kind' && '🥰 That\'s kind'}
          {state === 'bored' && '🥱 Getting sleepy...'}
          {(!['listening','thinking','speaking','greeting','happy','proud','thoughtful','funny','kind','bored'].includes(state)) && moodEmoji}
        </div>
      )}
    </div>
  )
}
