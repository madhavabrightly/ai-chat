import { useState, useEffect, useRef } from 'react'
import AnimeAvatarStage from './AnimeAvatarStage.jsx'
import CompanionSelector from './CompanionSelector.jsx'
import VoiceSelector from './VoiceSelector.jsx'
import { useChat } from '../context/ChatContext.jsx'
import { sendChatMessage } from '../api/memoryApi.js'
import { transcribeAudio } from '../api/asrApi.js'
import detectAvatarMood from '../utils/avatarMood.js'
import { guardAnswer } from '../utils/languageGuard.js'
import { speakText, stopSpeaking, isSpeaking } from '../utils/voiceEngine.js'
import { hasTempImport, getTempImportMeta, getTempImportData } from '../utils/tempImportStore.js'
import { startVadRecording, stopVadRecording, pauseVad, resumeVad, isVadActive } from '../utils/vadRecorder.js'

export default function LiveCallScreen() {
  const { addMessage } = useChat()
  const [companion, setCompanion] = useState(() => localStorage.getItem('mt_companion') || null)
  const [callStatus, setCallStatus] = useState('idle')
  const [avatarState, setAvatarState] = useState('idle')
  const [avatarMood, setAvatarMood] = useState('calm')
  const [lastUserText, setLastUserText] = useState('')
  const [lastAiText, setLastAiText] = useState('')
  const [callLog, setCallLog] = useState([])
  const [muted, setMuted] = useState(false)
  const [typedInput, setTypedInput] = useState('')
  const [showDebug, setShowDebug] = useState(false)
  const [debug, setDebug] = useState([])
  const [senderror, setSenderror] = useState('')
  const [transcribing, setTranscribing] = useState(false)
  const endRef = useRef(null)
  const processingRef = useRef(false)
  const restartTimerRef = useRef(null)
  const callStatusRef = useRef(callStatus)
  const typedRef = useRef(null)

  useEffect(() => { callStatusRef.current = callStatus }, [callStatus])

  const addDebug = (msg) => {
    console.log(`[LIVE_CALL] ${msg}`)
    setDebug(prev => [...prev.slice(-20), { msg, t: new Date().toLocaleTimeString() }])
  }

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [lastUserText, lastAiText, callLog, debug])
  useEffect(() => { return () => { if (restartTimerRef.current) clearTimeout(restartTimerRef.current) } }, [])

  function setCS(s) { setCallStatus(s); callStatusRef.current = s }
  function addLog(r, c) { setCallLog(prev => [...prev, { role: r, content: c, id: Date.now() }]) }

  async function sendTranscriptToChat(text) {
    if (!text || processingRef.current) return
    processingRef.current = true
    setSenderror('')
    addDebug(`sending_to_chat="${text.slice(0, 60)}..."`)
    setLastUserText(text)
    addLog('user', text)
    setCS('sending_to_chat')
    setAvatarState('thinking')

    const tempCtx = hasTempImport() ? {
      enabled: true, file_name: getTempImportMeta()?.file_name || '',
      summary: getTempImportMeta()?.summary || '',
      style_profile: { tone: getTempImportMeta()?.tone || 'warm' },
      chunks: getTempImportData(),
    } : null

    try {
      addDebug('awaiting /chat...')
      const data = await sendChatMessage({ question: text, companionType: companion || 'female', tempContext: tempCtx })
      addDebug(`chat_resp ok=${data.ok} err=${data.error || 'none'}`)

      if (!data.ok) {
        setLastAiText(data.answer || 'Backend error.')
        setSenderror(data.error || 'API error')
        setAvatarState('thoughtful')
        processingRef.current = false
        restartTimerRef.current = setTimeout(() => { if (callStatusRef.current !== 'ended') { setCS('listening'); setAvatarState('listening'); resumeVad() } }, 2000)
        return
      }

      const safeAnswer = guardAnswer(data.answer)
      setLastAiText(safeAnswer)
      addLog('assistant', safeAnswer)
      if (addMessage) addMessage('user', text)
      const mood = detectAvatarMood(safeAnswer, data.retrieved_memories || [])
      setAvatarMood(mood)
      setCS('ai_speaking')
      setAvatarState('speaking')

      if (!muted) {
        speakText(safeAnswer, {
          companionType: companion || 'female',
          onEnd: () => {
            addDebug('tts_ended')
            setAvatarState(mood)
            processingRef.current = false
            restartTimerRef.current = setTimeout(() => {
              if (callStatusRef.current !== 'ended') {
                addDebug('restart_vad')
                setCS('listening'); setAvatarState('listening'); resumeVad()
              }
            }, 1000)
          },
        })
      } else {
        setAvatarState(mood)
        processingRef.current = false
        restartTimerRef.current = setTimeout(() => {
          if (callStatusRef.current !== 'ended') {
            setCS('listening'); setAvatarState('listening'); resumeVad()
          }
        }, 1000)
      }
    } catch (e) {
      addDebug(`chat_error=${e.message}`)
      setLastAiText('Backend error. Try again.')
      setSenderror(e.message)
      setAvatarState('thoughtful')
      processingRef.current = false
      restartTimerRef.current = setTimeout(() => { if (callStatusRef.current !== 'ended') { setCS('listening'); setAvatarState('listening'); resumeVad() } }, 2000)
    }
  }

  // VAD callbacks
  function handleVadSpeechStart() {
    addDebug('speech_start')
    setCS('user_speaking')
    setAvatarState('listening')
  }

  async function handleVadSpeechEnd(audioBlob) {
    addDebug(`speech_end blob_size=${audioBlob.size}`)
    pauseVad()
    setTranscribing(true)
    setCS('user_speaking')

    addDebug('asr_request...')
    const asr = await transcribeAudio(audioBlob)
    setTranscribing(false)
    addDebug(`asr_resp ok=${asr.ok} transcript="${(asr.transcript || '').slice(0, 60)}..." err=${asr.error || 'none'}`)

    if (!asr.ok) {
      addDebug(`asr_failed=${asr.error}`)
      setSenderror('ASR: ' + (asr.error || 'failed'))
      setAvatarState('thoughtful')
      setTimeout(() => { if (callStatusRef.current !== 'ended') { setCS('listening'); setAvatarState('listening'); resumeVad() } }, 1500)
      return
    }

    const transcript = asr.transcript.trim()
    if (!transcript) {
      setTimeout(() => { if (callStatusRef.current !== 'ended') { setCS('listening'); setAvatarState('listening'); resumeVad() } }, 500)
      return
    }

    await sendTranscriptToChat(transcript)
  }

  function handleVadError(e) {
    addDebug(`vad_error=${e.message || 'unknown'}`)
    setSenderror('VAD error — type instead')
    setAvatarState('thoughtful')
  }

  async function startCall() {
    if (!companion) return
    setSenderror('')
    setLastUserText(''); setLastAiText(''); setDebug([]); addDebug('start_call')
    setCS('requesting_mic')

    const ok = await startVadRecording({ onSpeechStart: handleVadSpeechStart, onSpeechEnd: handleVadSpeechEnd, onError: handleVadError })
    if (ok) {
      setCS('listening'); setAvatarState('listening')
    } else {
      setCS('error')
    }
  }

  function endCall() {
    stopVadRecording(); stopSpeaking()
    if (restartTimerRef.current) clearTimeout(restartTimerRef.current)
    setCS('ended'); setAvatarState('idle'); processingRef.current = false
    addDebug('end_call')
  }

  function sendTyped() {
    const t = typedInput.trim()
    if (!t) return
    setTypedInput('')
    sendTranscriptToChat(t)
  }

  function resetCall() {
    stopVadRecording(); stopSpeaking()
    if (restartTimerRef.current) clearTimeout(restartTimerRef.current)
    setCS('idle'); setAvatarState('idle'); setSenderror('')
    processingRef.current = false; addDebug('reset')
  }

  const isRunning = callStatus !== 'idle' && callStatus !== 'ended'

  return (
    <div className="screen livecall-s">
      <div className="livecall-layout">
        <div className="livecall-main">
          <div className="livecall-stage">
            {companion ? (
              <AnimeAvatarStage companion={companion} state={avatarState} mood={avatarMood} isSpeaking={isSpeaking() && !muted} />
            ) : (
              <div className="livecall-no-comp"><p>Choose a companion to start.</p></div>
            )}
            <div className={`livecall-status-badge ${callStatus}`}>
              {callStatus === 'listening' && '🎤 Listening...'}
              {callStatus === 'user_speaking' && (transcribing ? '⏳ Transcribing...' : '🗣️ You are speaking...')}
              {callStatus === 'sending_to_chat' && '⏳ Sending to Memory Twin...'}
              {callStatus === 'ai_speaking' && '💬 AI speaking...'}
              {callStatus === 'ended' && '📴 Call ended'}
              {callStatus === 'error' && '⚠️ Error'}
              {callStatus === 'idle' && '📞 Ready'}
            </div>
          </div>

          {/* Transcript + typed */}
          <div className="livecall-transcript">
            {callStatus === 'listening' && !lastUserText && <div className="lc-interim">Listening for your voice...</div>}
            {lastUserText && <div className="lc-user-msg">You: {lastUserText}</div>}
            {lastAiText && <div className="lc-ai-msg">Memory Twin: {lastAiText}</div>}
            {senderror && <div className="lc-error">⚠️ {senderror}</div>}
            {transcribing && <div className="lc-interim">⏳ Transcribing your speech...</div>}

            {isRunning && (
              <div className="livecall-input-row">
                <input ref={typedRef} className="wa-input" placeholder="Type here and send..." value={typedInput}
                  onChange={e => setTypedInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendTyped() } }} />
                <button className="wa-send" onClick={sendTyped} disabled={!typedInput.trim()}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/>
                    <path d="m21.854 2.147-10.94 10.939"/>
                  </svg>
                </button>
              </div>
            )}
            <div className="lc-ethics">VAD + ASR pipeline. Mic pauses during AI speech.</div>
          </div>

          {/* Call log */}
          <div className="livecall-log">
            {callLog.filter(m => m.role !== 'system').slice(-8).map(m => (
              <div key={m.id} className="lc-log-msg">
                <span className="lc-log-label">{m.role === 'user' ? 'You' : 'Twin'}</span>
                <span className="lc-log-text">{m.content.slice(0, 100)}{m.content.length > 100 ? '...' : ''}</span>
              </div>
            ))}
            <div ref={endRef} />
          </div>

          {/* Debug */}
          <div className="livecall-debug-toggle" onClick={() => setShowDebug(!showDebug)}>
            {showDebug ? '🔽 Hide Debug' : '▶ Show Debug'}
          </div>
          {showDebug && (
            <div className="livecall-debug">
              <div>VAD: {isVadActive() ? '✅' : '❌'} | Status: {callStatus} | Speak: {isSpeaking() ? '✅' : '❌'}</div>
              <div>Transcribing: {transcribing ? '✅' : '❌'} | Proc: {processingRef.current ? '✅' : '❌'}</div>
              <div className="debug-log">{debug.map((d, i) => <div key={i} className="debug-line"><span className="debug-t">{d.t}</span> {d.msg}</div>)}</div>
            </div>
          )}
        </div>

        {/* Right panel */}
        <div className="livecall-side">
          {!companion ? (
            <CompanionSelector selected={companion} onSelect={(g) => { setCompanion(g); localStorage.setItem('mt_companion', g) }} />
          ) : (
            <div className="livecall-side-inner">
              <div className="livecall-comp-info">
                <span className="livecall-comp-icon">{companion === 'male' ? '👤' : '👩'}</span>
                <span>{companion === 'male' ? 'Male' : 'Female'}</span>
                <button className="btn-ghost-xs" onClick={() => { localStorage.removeItem('mt_companion'); setCompanion(null) }}>Change</button>
              </div>
              <VoiceSelector companionType={companion} />
              <div className="livecall-controls">
                {!isRunning && <button className="btn-primary" onClick={startCall} disabled={!companion}>📞 Start Call</button>}
                {isRunning && (
                  <>
                    <button className="btn-primary" onClick={endCall} style={{ background: '#a03030' }}>📴 End Call</button>
                    <button className="btn-ghost-sm" onClick={resetCall}>🔄 Reset</button>
                    <button className="btn-ghost-xs" onClick={() => setMuted(!muted)}>{muted ? '🔇 Voice Off' : '🔊 Voice On'}</button>
                  </>
                )}
              </div>
              {hasTempImport() && (
                <div className="temp-ctx-panel" style={{ borderTop: '1px solid #e8dac8' }}>
                  <div className="temp-ctx-title">📥 Temp Context Active</div>
                  <div className="temp-ctx-file">{getTempImportMeta()?.file_name}</div>
                </div>
              )}
              <div className="livecall-note">VAD → SenseVoice ASR → /chat → TTS → avatar. Mic paused while AI speaks.</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
