import { useState, useEffect } from 'react'
import VirtualCompanion from '../avatar/VirtualCompanion.jsx'
import CompanionSelector from './CompanionSelector.jsx'
import VoiceSelector from './VoiceSelector.jsx'
import createAvatarActionPlan from '../utils/avatarActionPlan.js'
import {
  speakText,
  stopSpeaking,
  subscribeSpeaking,
  isSpeaking,
} from '../utils/voiceEngine.js'
import {
  hasTempImport,
  getTempImportMeta,
  getTempImportData,
  clearTempImport,
} from '../utils/tempImportStore.js'

/**
 * LiveAvatarPanel — displays the avatar, voice controls, and engine status.
 *
 * Props:
 *   - avatarState, avatarMood: avatar animation state
 *   - companion: canonical companion value ('male' | 'female')
 *   - onSelectCompanion: callback when user picks a companion
 *   - lastAnswer, lastUserMessage, lastRetrievedMemories: for action plan
 *   - muted, onMuteChange: voice mute control
 *   - engineStatus: { asr, retrieval, reranker, llm, tts, avatar } — from backend /compute
 */
export default function LiveAvatarPanel({
  avatarState,
  avatarMood,
  companion,
  onSelectCompanion,
  lastAnswer,
  muted,
  onMuteChange,
  autoSpeak,
  onAutoSpeakChange,
  lastUserMessage,
  lastRetrievedMemories,
  engineStatus,
}) {
  const [showPlan, setShowPlan] = useState(false)
  const [showTemp, setShowTemp] = useState(true)
  const [showTempChat, setShowTempChat] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [currentTtsOp, setCurrentTtsOp] = useState(null)

  // Subscribe to TTS speaking state (reactive)
  useEffect(() => {
    const unsub = subscribeSpeaking(setSpeaking)
    return unsub
  }, [])

  // Cleanup TTS on unmount
  useEffect(() => {
    return () => {
      if (currentTtsOp) {
        try { currentTtsOp.cancel() } catch {}
      }
    }
  }, [currentTtsOp])

  const actionPlan = lastAnswer
    ? createAvatarActionPlan(lastUserMessage || '', lastAnswer, lastRetrievedMemories || [])
    : null
  const tempMeta = hasTempImport() ? getTempImportMeta() : null

  function handleSpeak() {
    if (!lastAnswer) return
    if (currentTtsOp) {
      try { currentTtsOp.cancel() } catch {}
      setCurrentTtsOp(null)
      return
    }
    if (!muted) {
      const op = speakText(lastAnswer, {
        companionType: companion || 'female',
        onEnd: () => setCurrentTtsOp(null),
        onCancel: () => setCurrentTtsOp(null),
        onError: () => setCurrentTtsOp(null),
      })
      setCurrentTtsOp(op)
    }
  }

  function handleClearTemp() {
    clearTempImport()
    // No window.location.reload() — just clear state and let React re-render
  }

  // Engine status display — only show what backend actually reports
  const status = engineStatus || {}
  const engineRows = [
    { label: 'ASR', value: status.asr || '—', kind: status.asr?.includes('SenseVoice') ? 'ok' : 'fallback' },
    { label: 'Retrieval', value: status.retrieval || '—', kind: status.retrieval?.includes('Qwen3') ? 'ok' : 'fallback' },
    { label: 'Reranker', value: status.reranker || '—', kind: status.reranker?.includes('Qwen3') ? 'ok' : 'fallback' },
    { label: 'LLM', value: status.llm || '—', kind: status.llm?.includes('Qwen') ? 'ok' : 'fallback' },
    { label: 'TTS', value: status.tts || '—', kind: status.tts?.includes('CosyVoice') ? 'ok' : 'fallback' },
    { label: 'Avatar', value: status.avatar || 'Three.js GLB', kind: 'ok' },
  ]

  return (
    <div className="avatar-panel">
      <div className="avatar-panel-head">
        <div className="avatar-panel-title-row">
          {companion && <span className="comp-dot">{companion === 'male' ? '👤' : '👩'}</span>}
          <span className="avatar-panel-title">{companion ? 'Companion' : 'Choose Companion'}</span>
        </div>
        <button className="btn-ghost-xs" onClick={() => setShowPlan(!showPlan)} title="Action plan">
          {showPlan ? '🔍' : '📋'}
        </button>
      </div>

      <div className="avatar-panel-body">
        {!companion ? (
          <CompanionSelector selected={companion} onSelect={onSelectCompanion} />
        ) : (
          <>
            <VirtualCompanion
              companion={companion}
              state={avatarState}
              mood={avatarMood}
              isSpeaking={speaking && !muted}
              avatarPlan={actionPlan}
              variant="panel"
            />
            <VoiceSelector companionType={companion} />

            <div className="avatar-controls">
              <button
                className={`btn-ghost-xs ${muted ? 'btn-muted' : ''}`}
                onClick={() => {
                  onMuteChange(!muted)
                  if (!muted) {
                    if (currentTtsOp) {
                      try { currentTtsOp.cancel() } catch {}
                      setCurrentTtsOp(null)
                    }
                    stopSpeaking()
                  }
                }}
              >
                {muted ? '🔇 Off' : '🔊 Voice'}
              </button>
              <button
                className={`btn-ghost-xs ${autoSpeak ? 'btn-auto-on' : ''}`}
                onClick={() => onAutoSpeakChange && onAutoSpeakChange(!autoSpeak)}
                title={autoSpeak ? 'Auto-speak ON — every answer is spoken' : 'Auto-speak OFF — tap Replay to hear'}
              >
                {autoSpeak ? '🔔 Auto' : '🔕 Manual'}
              </button>
              <button className="btn-ghost-xs" onClick={handleSpeak} disabled={!lastAnswer}>
                {currentTtsOp ? '⏹ Stop' : '🔁 Replay'}
              </button>
            </div>

            <div className="avatar-info">
              <div className="avatar-info-row">
                <span>Companion</span>
                <span className="info-val">{companion === 'male' ? 'Male' : 'Female'}</span>
              </div>
              <div className="avatar-info-row">
                <span>Mood</span>
                <span className="info-val" style={{ textTransform: 'capitalize' }}>{avatarMood || 'calm'}</span>
              </div>
              <div className="avatar-info-row">
                <span>State</span>
                <span className="info-val" style={{ textTransform: 'capitalize' }}>{avatarState || 'idle'}</span>
              </div>
            </div>

            {/* Temporary Chat Context */}
            {tempMeta && showTemp && (
              <div className="temp-ctx-panel">
                <div className="temp-ctx-head">
                  <span className="temp-ctx-title">📥 Temp Context</span>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button className="btn-ghost-xs" onClick={() => setShowTempChat(true)} title="View imported chat">💬</button>
                    <button className="btn-ghost-xs" onClick={handleClearTemp} title="Clear temp context">✕</button>
                  </div>
                </div>
                <div className="temp-ctx-file">{tempMeta.file_name}</div>
                <div className="temp-ctx-summary">{tempMeta.summary}</div>
                <div className="temp-ctx-tags">
                  {tempMeta.tone && <span className="tag-s" style={{ background: '#c9a96e', color: '#fff' }}>{tempMeta.tone}</span>}
                  {(tempMeta.emotions || []).map(e => <span key={e} className="tag-s">{e}</span>)}
                </div>
                <button
                  className="btn-ghost-xs"
                  style={{ marginTop: 6, width: '100%', fontSize: '0.7rem' }}
                  onClick={() => setShowTempChat(true)}
                  title="Open the imported chat to browse and ask questions about it"
                >
                  💬 Chat in file
                </button>
              </div>
            )}

            {/* Temp Chat Modal — browse imported messages */}
            {showTempChat && tempMeta && (
              <TempChatModal
                meta={tempMeta}
                chunks={getTempImportData()}
                onClose={() => setShowTempChat(false)}
              />
            )}

            {/* Realtime Engine Status — only show what backend reports */}
            <div className="realtime-engine-panel">
              <div className="realtime-engine-title">⚡ Realtime Engine</div>
              <div className="realtime-engine-grid">
                {engineRows.map(row => (
                  <div key={row.label} className="realtime-engine-row">
                    <span>{row.label}</span>
                    <span className={row.kind === 'ok' ? 're-ok' : 're-fallback'}>{row.value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Avatar Action Plan (collapsible) */}
            {showPlan && actionPlan && (
              <div className="action-plan-panel">
                <div className="action-plan-title">🎬 Avatar Action Plan</div>
                <div className="action-plan-grid">
                  <div className="action-plan-row"><span className="ap-lbl">Mood</span><span className="ap-val" style={{ textTransform: 'capitalize' }}>{actionPlan.mood}</span></div>
                  <div className="action-plan-row"><span className="ap-lbl">Expression</span><span className="ap-val">{actionPlan.expression}</span></div>
                  <div className="action-plan-row"><span className="ap-lbl">Gesture</span><span className="ap-val">{actionPlan.gesture}</span></div>
                  <div className="action-plan-row"><span className="ap-lbl">Action</span><span className="ap-val">{actionPlan.recommendedAction}</span></div>
                  <div className="action-plan-row"><span className="ap-lbl">Reason</span><span className="ap-val" style={{ fontSize: '0.68rem' }}>{actionPlan.reason}</span></div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ── TempChatModal — browse and search imported chat messages ────────
function TempChatModal({ meta, chunks, onClose }) {
  const [search, setSearch] = useState('')
  const [filterSpeaker, setFilterSpeaker] = useState('')

  const speakers = [...new Set(chunks.map(c => c.speaker).filter(Boolean))]
  const filtered = chunks.filter(c => {
    if (filterSpeaker && c.speaker !== filterSpeaker) return false
    if (search && !c.text.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <div className="temp-chat-modal-overlay" onClick={onClose}>
      <div className="temp-chat-modal" onClick={e => e.stopPropagation()}>
        <div className="temp-chat-modal-head">
          <div>
            <div className="temp-chat-modal-title">💬 {meta.file_name}</div>
            <div className="temp-chat-modal-sub">{meta.summary}</div>
          </div>
          <button className="btn-ghost-xs" onClick={onClose}>✕</button>
        </div>
        <div className="temp-chat-modal-filters">
          <input
            type="text"
            placeholder="🔍 Search messages..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="temp-chat-search"
          />
          <select
            value={filterSpeaker}
            onChange={e => setFilterSpeaker(e.target.value)}
            className="temp-chat-speaker-filter"
          >
            <option value="">All speakers</option>
            {speakers.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="temp-chat-modal-body">
          {filtered.length === 0 ? (
            <div className="temp-chat-empty">No messages match your filter.</div>
          ) : (
            filtered.map((chunk, i) => (
              <div key={i} className="temp-chat-msg">
                <div className="temp-chat-msg-head">
                  <span className="temp-chat-speaker">{chunk.speaker}</span>
                  {chunk.date && <span className="temp-chat-date">{chunk.date}</span>}
                  {chunk.message_count > 1 && <span className="temp-chat-count">{chunk.message_count} msgs</span>}
                </div>
                <div className="temp-chat-text">{chunk.text}</div>
              </div>
            ))
          )}
        </div>
        <div className="temp-chat-modal-foot">
          <span>{filtered.length} of {chunks.length} messages</span>
          <span style={{ fontSize: '0.65rem', opacity: 0.7 }}>
            Ask questions in the main chat — the AI will answer from this imported context.
          </span>
        </div>
      </div>
    </div>
  )
}
