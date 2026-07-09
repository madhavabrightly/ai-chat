import { useState } from 'react'
import AnimeAvatarStage from './AnimeAvatarStage.jsx'
import CompanionSelector from './CompanionSelector.jsx'
import VoiceSelector from './VoiceSelector.jsx'
import createAvatarActionPlan from '../utils/avatarActionPlan.js'
import { speakText, stopSpeaking, isSpeaking } from '../utils/voiceEngine.js'
import { hasTempImport, getTempImportMeta, clearTempImport } from '../utils/tempImportStore.js'

export default function LiveAvatarPanel({
  avatarState, avatarMood, companion, onSelectCompanion,
  lastAnswer, gender, muted, onMuteChange, lastUserMessage, lastRetrievedMemories,
}) {
  const [showPlan, setShowPlan] = useState(false)
  const [showTemp, setShowTemp] = useState(true)

  const actionPlan = lastAnswer ? createAvatarActionPlan(lastUserMessage || '', lastAnswer, lastRetrievedMemories || []) : null
  const tempMeta = hasTempImport() ? getTempImportMeta() : null

  function handleSpeak() {
    if (!lastAnswer) return
    if (isSpeaking()) { stopSpeaking(); return }
    if (!muted) speakText(lastAnswer, { companionType: gender || 'female', onEnd: () => {} })
  }

  return (
    <div className="avatar-panel">
      <div className="avatar-panel-head">
        <div className="avatar-panel-title-row">
          {companion && <span className="comp-dot">{companion === 'male' ? '👤' : '👩'}</span>}
          <span className="avatar-panel-title">{companion ? 'Companion' : 'Choose Companion'}</span>
        </div>
        <button className="btn-ghost-xs" onClick={() => setShowPlan(!showPlan)} title="Action plan">{showPlan ? '🔍' : '📋'}</button>
      </div>

      <div className="avatar-panel-body">
        {!companion ? (
          <CompanionSelector selected={companion} onSelect={onSelectCompanion} />
        ) : (
          <>
            <AnimeAvatarStage companion={companion} state={avatarState} mood={avatarMood} isSpeaking={isSpeaking() && !muted} />
            <VoiceSelector companionType={companion} />

            <div className="avatar-controls">
              <button className={`btn-ghost-xs ${muted ? 'btn-muted' : ''}`} onClick={() => { onMuteChange(!muted); if (!muted) stopSpeaking() }}>
                {muted ? '🔇 Off' : '🔊 Voice'}
              </button>
              <button className="btn-ghost-xs" onClick={handleSpeak} disabled={!lastAnswer}>
                {isSpeaking() ? '⏹ Stop' : '🔁 Replay'}
              </button>
            </div>

            <div className="avatar-info">
              <div className="avatar-info-row"><span>Companion</span><span className="info-val">{companion === 'male' ? 'Male' : 'Female'}</span></div>
              <div className="avatar-info-row"><span>Mood</span><span className="info-val" style={{ textTransform: 'capitalize' }}>{avatarMood || 'calm'}</span></div>
              <div className="avatar-info-row"><span>State</span><span className="info-val" style={{ textTransform: 'capitalize' }}>{avatarState || 'idle'}</span></div>
            </div>

            {/* Temporary Chat Context */}
            {tempMeta && showTemp && (
              <div className="temp-ctx-panel">
                <div className="temp-ctx-head">
                  <span className="temp-ctx-title">📥 Temp Context</span>
                  <button className="btn-ghost-xs" onClick={() => { clearTempImport(); window.location.reload() }}>✕</button>
                </div>
                <div className="temp-ctx-file">{tempMeta.file_name}</div>
                <div className="temp-ctx-summary">{tempMeta.summary}</div>
                <div className="temp-ctx-tags">
                  {tempMeta.tone && <span className="tag-s" style={{ background: '#c9a96e', color: '#fff' }}>{tempMeta.tone}</span>}
                  {(tempMeta.emotions || []).map(e => <span key={e} className="tag-s">{e}</span>)}
                </div>
              </div>
            )}

            {/* Realtime Engine Status */}
            <div className="realtime-engine-panel">
              <div className="realtime-engine-title">⚡ Realtime Engine</div>
              <div className="realtime-engine-grid">
                <div className="realtime-engine-row"><span>ASR</span><span className="re-fallback">Browser</span></div>
                <div className="realtime-engine-row"><span>Emotion</span><span className="re-fallback">Heuristic</span></div>
                <div className="realtime-engine-row"><span>Retrieval</span><span className="re-ok">Qwen3 Embed</span></div>
                <div className="realtime-engine-row"><span>Reranker</span><span className="re-fallback">Qwen3 (pending)</span></div>
                <div className="realtime-engine-row"><span>LLM</span><span className="re-ok">Qwen2.5-7B</span></div>
                <div className="realtime-engine-row"><span>TTS</span><span className="re-fallback">Browser</span></div>
                <div className="realtime-engine-row"><span>Avatar</span><span className="re-ok">Live CSS</span></div>
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
