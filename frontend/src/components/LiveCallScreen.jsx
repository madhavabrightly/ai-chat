import { useState, useEffect, useRef, useCallback } from 'react'
import VirtualCompanion from '../avatar/VirtualCompanion.jsx'
import CompanionSelector from './CompanionSelector.jsx'
import VoiceSelector from './VoiceSelector.jsx'
import { useChat } from '../context/ChatContext.jsx'
import { transcribeAudio } from '../api/asrApi.js'
import { requestAvatarAction, sendChatMessageStream } from '../api/memoryApi.js'
import detectAvatarMood from '../utils/avatarMood.js'
import { guardAnswer } from '../utils/languageGuard.js'
import {
  createSpeechQueue,
  stopSpeaking,
  subscribeSpeaking,
} from '../utils/voiceEngine.js'
import {
  startVad,
  startBrowserSR,
  stopAll as stopTranscribing,
  subscribeActiveState,
  getActiveState,
  getTranscriberMode,
  hasBrowserSpeechRecognition,
  TRANSCRIBER_MODE,
} from '../utils/activeTranscriber.js'
import {
  hasTempImport,
  getTempImportMeta,
  getTempImportData,
} from '../utils/tempImportStore.js'

const CALL_STATE = Object.freeze({
  IDLE: 'idle',
  REQUESTING_MIC: 'requesting_mic',
  LISTENING: 'listening',
  USER_SPEAKING: 'user_speaking',
  THINKING: 'thinking',
  AI_SPEAKING: 'ai_speaking',
  INTERRUPTED: 'interrupted',
  ENDED: 'ended',
  ERROR: 'error',
})

const SPEECH_FLUSH_MS = 320
const DUPLICATE_TRANSCRIPT_MS = 1400

function normalizeForSpeech(text) {
  return String(text || '')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/https?:\/\/\S+/g, ' ')
    .replace(/[#*_>~]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function splitSpeakablePhrases(buffer, force = false) {
  let remaining = String(buffer || '').replace(/\s+/g, ' ').trimStart()
  const phrases = []

  while (remaining.trim()) {
    const sentence = remaining.match(/[.!?](?=\s|$)/)
    if (sentence && sentence.index >= 8) {
      const end = sentence.index + 1
      phrases.push(remaining.slice(0, end).trim())
      remaining = remaining.slice(end).trimStart()
      continue
    }

    const words = remaining.trim().split(/\s+/)
    if (words.length >= 10) {
      const chunk = words.slice(0, 10).join(' ')
      phrases.push(chunk)
      remaining = words.slice(10).join(' ')
      continue
    }

    if (force) {
      phrases.push(remaining.trim())
      remaining = ''
    }
    break
  }

  return { phrases, rest: remaining }
}

export default function LiveCallScreen() {
  const { addMessage } = useChat()
  const [companion, setCompanion] = useState(() => localStorage.getItem('mt_companion') || null)
  const [callState, setCallState] = useState(CALL_STATE.IDLE)
  const [avatarState, setAvatarState] = useState('idle')
  const [avatarMood, setAvatarMood] = useState('calm')
  const [avatarPlan, setAvatarPlan] = useState(null)
  const [lastUserText, setLastUserText] = useState('')
  const [lastAiText, setLastAiText] = useState('')
  const [partialText, setPartialText] = useState('')
  const [callLog, setCallLog] = useState([])
  const [muted, setMuted] = useState(false)
  const [typedInput, setTypedInput] = useState('')
  const [showDebug, setShowDebug] = useState(false)
  const [debug, setDebug] = useState([])
  const [senderror, setSenderror] = useState('')
  const [speaking, setSpeaking] = useState(false)

  const callStateRef = useRef(callState)
  const companionRef = useRef(companion)
  const mutedRef = useRef(muted)
  const processingRef = useRef(false)
  const currentTtsOpRef = useRef(null)
  const currentAbortRef = useRef(null)
  const callSessionRef = useRef(null)
  const responseGenerationRef = useRef(0)
  const phraseBufferRef = useRef('')
  const phraseTimerRef = useRef(null)
  const callLogRef = useRef([])
  const lastTranscriptRef = useRef({ text: '', at: 0 })
  const endRef = useRef(null)
  const typedRef = useRef(null)

  useEffect(() => { callStateRef.current = callState }, [callState])
  useEffect(() => { companionRef.current = companion }, [companion])
  useEffect(() => { mutedRef.current = muted }, [muted])

  const addDebug = useCallback((msg) => {
    console.log(`[LIVE_CALL] ${msg}`)
    setDebug(prev => [...prev.slice(-20), { msg, t: new Date().toLocaleTimeString() }])
  }, [])

  useEffect(() => subscribeSpeaking(setSpeaking), [])

  useEffect(() => {
    const unsub = subscribeActiveState((state) => {
      addDebug(`recognition=${state}`)
    })
    return unsub
  }, [addDebug])

  useEffect(() => {
    return () => {
      clearPhraseTimer()
      cancelActiveResponse('unmount')
      stopTranscribing()
      stopSpeaking()
    }
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lastUserText, lastAiText, partialText, callLog, debug])

  function transitionCallState(newState) {
    callStateRef.current = newState
    setCallState(newState)
  }

  function setCallLogSynced(updater) {
    setCallLog(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater
      callLogRef.current = next
      return next
    })
  }

  function addLog(role, content) {
    setCallLogSynced(prev => [...prev, { role, content, id: Date.now() + Math.random() }])
  }

  function clearPhraseTimer() {
    if (phraseTimerRef.current) {
      clearTimeout(phraseTimerRef.current)
      phraseTimerRef.current = null
    }
  }

  function finishTurn(generationId, mood = 'calm') {
    if (responseGenerationRef.current !== generationId) return
    currentTtsOpRef.current = null
    processingRef.current = false
    phraseBufferRef.current = ''
    clearPhraseTimer()
    setAvatarState(mood)
    if (callStateRef.current !== CALL_STATE.ENDED) {
      transitionCallState(CALL_STATE.LISTENING)
    }
  }

  function cancelActiveResponse(reason = 'cancel') {
    responseGenerationRef.current += 1
    clearPhraseTimer()
    phraseBufferRef.current = ''
    if (currentAbortRef.current) {
      try { currentAbortRef.current.abort() } catch {}
      currentAbortRef.current = null
    }
    if (currentTtsOpRef.current) {
      try { currentTtsOpRef.current.cancel() } catch {}
      currentTtsOpRef.current = null
    }
    stopSpeaking()
    processingRef.current = false
    addDebug(`cancel_response=${reason}`)
  }

  function buildTempContext() {
    if (!hasTempImport()) return null
    return {
      enabled: true,
      session_id: getTempImportMeta()?.session_id || '',
      file_name: getTempImportMeta()?.file_name || '',
      summary: getTempImportMeta()?.summary || '',
      style_profile: {
        tone: getTempImportMeta()?.tone || 'warm',
        chat_style: 'Adapted from imported chat',
        emotions: getTempImportMeta()?.emotions || [],
      },
      chunks: getTempImportData(),
    }
  }

  function buildHistory() {
    return callLogRef.current
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .slice(-10)
      .map(m => ({ role: m.role, content: m.content }))
  }

  function queueSpeechFromBuffer(speechQueue, force = false) {
    if (!speechQueue) return
    const { phrases, rest } = splitSpeakablePhrases(phraseBufferRef.current, force)
    phraseBufferRef.current = rest
    for (const phrase of phrases) {
      const clean = normalizeForSpeech(phrase)
      if (clean) speechQueue.enqueue(clean)
    }
  }

  function schedulePhraseFlush(generationId, speechQueue) {
    clearPhraseTimer()
    if (!speechQueue) return
    phraseTimerRef.current = setTimeout(() => {
      phraseTimerRef.current = null
      if (responseGenerationRef.current !== generationId) return
      const words = phraseBufferRef.current.trim().split(/\s+/).filter(Boolean)
      if (words.length >= 6) {
        queueSpeechFromBuffer(speechQueue, true)
      }
    }, SPEECH_FLUSH_MS)
  }

  async function sendTranscriptToChat(text) {
    const transcript = String(text || '').replace(/\s+/g, ' ').trim()
    if (!transcript || callStateRef.current === CALL_STATE.ENDED) return

    if (currentAbortRef.current || currentTtsOpRef.current || processingRef.current) {
      cancelActiveResponse('superseded')
    }

    const generationId = responseGenerationRef.current + 1
    responseGenerationRef.current = generationId

    const abortController = new AbortController()
    currentAbortRef.current = abortController
    processingRef.current = true
    phraseBufferRef.current = ''
    setSenderror('')
    setPartialText('')
    setLastUserText(transcript)
    setLastAiText('')
    setAvatarPlan({ mood: avatarMood, movement: 'listening', gesture: 'attentive' })
    addLog('user', transcript)
    transitionCallState(CALL_STATE.THINKING)
    setAvatarState('thinking')
    addDebug(`stream_start="${transcript.slice(0, 80)}"`)

    const history = buildHistory()
    const tempContext = buildTempContext()
    let fullAnswer = ''
    let retrievedMemories = []
    let finalHandled = false
    let firstTokenSeen = false
    let mood = 'calm'

    const speechQueue = mutedRef.current ? null : createSpeechQueue({
      companionType: companionRef.current || 'female',
      onStart: () => {
        if (responseGenerationRef.current !== generationId) return
        addDebug('voice_started')
        transitionCallState(CALL_STATE.AI_SPEAKING)
        setAvatarState('speaking')
      },
      onEnd: () => {
        addDebug('voice_ended')
        finishTurn(generationId, mood)
      },
      onCancel: () => {
        addDebug('voice_cancelled')
      },
      onError: (e) => {
        addDebug(`voice_error=${e?.error || e?.message || 'unknown'}`)
        finishTurn(generationId, mood)
      },
    })
    currentTtsOpRef.current = speechQueue

    try {
      const result = await sendChatMessageStream({
        question: transcript,
        companionType: companionRef.current || 'female',
        history,
        tempContext,
        voiceMode: true,
        signal: abortController.signal,
        onToken: (delta) => {
          if (responseGenerationRef.current !== generationId) return
          if (currentAbortRef.current !== abortController) return
          if (!delta) return

          fullAnswer += delta
          setLastAiText(guardAnswer(fullAnswer))
          if (!firstTokenSeen) {
            firstTokenSeen = true
            transitionCallState(CALL_STATE.AI_SPEAKING)
            setAvatarState(mutedRef.current ? 'thoughtful' : 'speaking')
            addDebug('first_token')
          }

          phraseBufferRef.current += delta
          queueSpeechFromBuffer(speechQueue, false)
          schedulePhraseFlush(generationId, speechQueue)
        },
        onTrace: (trace) => {
          if (responseGenerationRef.current !== generationId) return
          addDebug(`retrieval_ms=${trace?.retrieval_ms || trace?.ms || 0}`)
        },
        onAvatarAction: (plan) => {
          if (responseGenerationRef.current !== generationId) return
          setAvatarPlan(plan || null)
          if (plan?.mood) {
            mood = plan.mood
            setAvatarMood(plan.mood)
          }
          addDebug(`avatar_action=${plan?.movement || plan?.gesture || plan?.mood || 'plan'}`)
        },
        onDone: (done) => {
          if (responseGenerationRef.current !== generationId) return
          if (finalHandled && !done?.answer) return
          finalHandled = true

          const safeAnswer = guardAnswer(done?.answer || fullAnswer).trim()
          fullAnswer = safeAnswer
          retrievedMemories = done?.retrieved_memories || retrievedMemories
          mood = detectAvatarMood(safeAnswer, retrievedMemories)
          if (done?.avatar_action_plan) {
            setAvatarPlan(done.avatar_action_plan)
            if (done.avatar_action_plan.mood) mood = done.avatar_action_plan.mood
          }
          setAvatarMood(mood)
          setLastAiText(safeAnswer)
          addLog('assistant', safeAnswer)
          addDebug(`stream_done chars=${safeAnswer.length}`)

          void requestAvatarAction({
            answer: safeAnswer,
            retrievedMemories,
            companionType: companionRef.current || 'female',
          }).then((result) => {
            if (responseGenerationRef.current !== generationId) return
            if (!result?.ok || !result.plan) return
            setAvatarPlan(result.plan)
            if (result.plan.mood) {
              mood = result.plan.mood
              setAvatarMood(result.plan.mood)
            }
            addDebug(`motion_director=${result.plan.director || 'instant_rules'}`)
          }).catch((error) => {
            addDebug(`motion_director_error=${error?.message || 'unavailable'}`)
          })

          if (addMessage) {
            const requestId = done?.request_id || `live_${Date.now()}`
            addMessage('user', transcript, { request_id: requestId })
            addMessage('assistant', safeAnswer, {
              request_id: requestId,
              memory_based: retrievedMemories.length > 0,
              retrieved_memories: retrievedMemories,
              status: 'complete',
            })
          }

          queueSpeechFromBuffer(speechQueue, true)
          if (speechQueue) {
            speechQueue.close()
          } else {
            finishTurn(generationId, mood)
          }
        },
        onError: (err) => {
          if (responseGenerationRef.current !== generationId) return
          if (err?.code === 'CANCELLED') return
          const message = err?.message || 'Live response failed. Try again.'
          addDebug(`stream_error=${message}`)
          setSenderror(message)
          transitionCallState(CALL_STATE.ERROR)
          setAvatarState('thoughtful')
          if (speechQueue) {
            try { speechQueue.cancel() } catch {}
          }
          finishTurn(generationId, 'thoughtful')
        },
      })

      if (!result.ok && result.code !== 'CANCELLED' && responseGenerationRef.current === generationId) {
        setSenderror(result.code || 'Stream error')
        transitionCallState(CALL_STATE.ERROR)
        finishTurn(generationId, 'thoughtful')
      }
    } catch (e) {
      if (abortController.signal.aborted) return
      if (responseGenerationRef.current !== generationId) return
      addDebug(`stream_exception=${e.message}`)
      setSenderror(e.message || 'Live response failed.')
      transitionCallState(CALL_STATE.ERROR)
      finishTurn(generationId, 'thoughtful')
    } finally {
      if (currentAbortRef.current === abortController) {
        currentAbortRef.current = null
      }
      if (!speechQueue && responseGenerationRef.current === generationId) {
        processingRef.current = false
      }
    }
  }

  function handleSpeechStart() {
    if (callStateRef.current === CALL_STATE.ENDED) return
    if (
      callStateRef.current === CALL_STATE.AI_SPEAKING ||
      callStateRef.current === CALL_STATE.THINKING ||
      processingRef.current
    ) {
      cancelActiveResponse('barge_in')
      transitionCallState(CALL_STATE.INTERRUPTED)
      setTimeout(() => {
        if (callStateRef.current === CALL_STATE.INTERRUPTED) {
          transitionCallState(CALL_STATE.USER_SPEAKING)
        }
      }, 120)
    } else {
      transitionCallState(CALL_STATE.USER_SPEAKING)
    }
    setAvatarState('listening')
  }

  function handleInterimTranscript(text) {
    if (callStateRef.current === CALL_STATE.ENDED) return
    const transcript = String(text || '').replace(/\s+/g, ' ').trim()
    if (!transcript) return
    setPartialText(transcript)
    if (callStateRef.current !== CALL_STATE.USER_SPEAKING) {
      transitionCallState(CALL_STATE.USER_SPEAKING)
    }
  }

  function handleFinalTranscript(text) {
    if (callStateRef.current === CALL_STATE.ENDED) return
    const transcript = String(text || '').replace(/\s+/g, ' ').trim()
    setPartialText('')
    if (!transcript) {
      transitionCallState(CALL_STATE.LISTENING)
      return
    }

    const now = Date.now()
    if (
      transcript.toLowerCase() === lastTranscriptRef.current.text.toLowerCase() &&
      now - lastTranscriptRef.current.at < DUPLICATE_TRANSCRIPT_MS
    ) {
      addDebug('duplicate_transcript_skipped')
      transitionCallState(CALL_STATE.LISTENING)
      return
    }
    lastTranscriptRef.current = { text: transcript, at: now }
    sendTranscriptToChat(transcript)
  }

  function handleSpeechError(e) {
    const message = e?.code === 'MIC_PERMISSION_DENIED'
      ? 'Microphone permission is blocked. Allow the mic in the browser and start again.'
      : (e?.message || e?.code || 'Speech recognition failed.')
    addDebug(`speech_error=${message}`)
    setSenderror(message)
    setAvatarState('thoughtful')
    transitionCallState(CALL_STATE.ERROR)
  }

  async function handleSpeechAudio(audioBlob, sessionToken) {
    if (callStateRef.current === CALL_STATE.ENDED) return
    setPartialText('Transcribing...')
    addDebug(`asr_audio_bytes=${audioBlob?.size || 0}`)
    const result = await transcribeAudio(audioBlob)
    if (callSessionRef.current?.token !== sessionToken) return
    if (result.ok && result.transcript) {
      addDebug(`asr_model=${result.asr_model || 'backend'}`)
      handleFinalTranscript(result.transcript)
      return
    }
    setPartialText('')
    addDebug(`asr_failed=${result.error || result.code || 'unknown'}`)
    handleSpeechError({
      code: result.code || 'ASR_FAILED',
      message: result.fallback
        ? 'Backend ASR is unavailable. Install FunASR/SenseVoice dependencies, or use browser fallback.'
        : (result.error || 'ASR failed.'),
    })
  }

  async function startCall() {
    if (!companion) return
    setSenderror('')
    setLastUserText('')
    setLastAiText('')
    setPartialText('')
    setAvatarPlan(null)
    setDebug([])
    callLogRef.current = []
    setCallLog([])
    addDebug('start_call')
    transitionCallState(CALL_STATE.REQUESTING_MIC)

    callSessionRef.current = { token: `call_${Date.now()}`, startedAt: Date.now() }
    const sessionToken = callSessionRef.current.token

    const vadResult = await startVad({
      onSpeechStart: () => {
        if (callSessionRef.current?.token !== sessionToken) return
        handleSpeechStart()
      },
      onSpeechEnd: (audioBlob) => {
        if (callSessionRef.current?.token !== sessionToken) return
        handleSpeechAudio(audioBlob, sessionToken)
      },
      onError: (e) => {
        if (callSessionRef.current?.token !== sessionToken) return
        addDebug(`vad_error=${e?.message || e?.code || 'unknown'}`)
      },
    })

    let result = vadResult
    if (!vadResult.ok) {
      if (!hasBrowserSpeechRecognition()) {
        setSenderror('Live speech is not available. VAD failed and browser speech fallback is unavailable.')
        transitionCallState(CALL_STATE.ERROR)
        return
      }
      addDebug(`vad_fallback_browser_sr=${vadResult.error || 'init_failed'}`)
      result = startBrowserSR({
        onSpeechStart: () => {
          if (callSessionRef.current?.token !== sessionToken) return
          handleSpeechStart()
        },
        onInterim: (text) => {
          if (callSessionRef.current?.token !== sessionToken) return
          handleInterimTranscript(text)
        },
        onFinal: (text) => {
          if (callSessionRef.current?.token !== sessionToken) return
          handleFinalTranscript(text)
        },
        onError: (e) => {
          if (callSessionRef.current?.token !== sessionToken) return
          handleSpeechError(e)
        },
      })
    }

    if (result.ok) {
      const mode = getTranscriberMode()
      addDebug(`transcriber=${mode}`)
      if (mode === TRANSCRIBER_MODE.VAD) {
        addDebug('asr_route=backend_sensevoice')
      }
      transitionCallState(CALL_STATE.LISTENING)
      setAvatarState('listening')
    } else {
      transitionCallState(CALL_STATE.ERROR)
      setSenderror('Failed to start microphone: ' + (result.error || 'unknown'))
    }
  }

  function endCall() {
    addDebug('end_call')
    cancelActiveResponse('end_call')
    stopTranscribing()
    stopSpeaking()
    callSessionRef.current = null
    processingRef.current = false
    setPartialText('')
    transitionCallState(CALL_STATE.ENDED)
    setAvatarState('idle')
    setAvatarPlan(null)
  }

  function sendTyped() {
    const text = typedInput.trim()
    if (!text) return
    setTypedInput('')
    setPartialText('')
    sendTranscriptToChat(text)
  }

  function resetCall() {
    addDebug('reset')
    cancelActiveResponse('reset')
    stopTranscribing()
    stopSpeaking()
    callSessionRef.current = null
    processingRef.current = false
    setSenderror('')
    setPartialText('')
    transitionCallState(CALL_STATE.IDLE)
    setAvatarState('idle')
    setAvatarPlan(null)
  }

  const isRunning = callState !== CALL_STATE.IDLE && callState !== CALL_STATE.ENDED

  return (
    <div className="screen livecall-s">
      <div className="livecall-layout">
        <div className="livecall-main">
          <div className="livecall-stage">
            {companion ? (
              <VirtualCompanion
                companion={companion}
                state={avatarState}
                mood={avatarMood}
                isSpeaking={speaking && !muted}
                avatarPlan={avatarPlan}
                variant="livecall"
              />
            ) : (
              <div className="livecall-no-comp"><p>Choose a companion to start.</p></div>
            )}
            <div className={`livecall-status-badge ${callState}`}>
              {callState === CALL_STATE.LISTENING && '🎤 Listening...'}
              {callState === CALL_STATE.USER_SPEAKING && '🗣️ Hearing you...'}
              {callState === CALL_STATE.THINKING && '⚡ Thinking...'}
              {callState === CALL_STATE.AI_SPEAKING && '💬 Speaking...'}
              {callState === CALL_STATE.INTERRUPTED && '⏹️ Interrupted'}
              {callState === CALL_STATE.ENDED && '📴 Call ended'}
              {callState === CALL_STATE.ERROR && '⚠️ Error'}
              {callState === CALL_STATE.IDLE && '📞 Ready'}
              {callState === CALL_STATE.REQUESTING_MIC && '🎙️ Starting microphone...'}
            </div>
          </div>

          <div className="livecall-transcript">
            {callState === CALL_STATE.LISTENING && !lastUserText && !partialText && (
              <div className="lc-interim">Listening for your voice...</div>
            )}
            {partialText && <div className="lc-interim">Hearing: {partialText}</div>}
            {lastUserText && <div className="lc-user-msg">You: {lastUserText}</div>}
            {lastAiText && <div className="lc-ai-msg">Memory Twin: {lastAiText}</div>}
            {senderror && <div className="lc-error">⚠️ {senderror}</div>}

            {isRunning && (
              <div className="livecall-input-row">
                <input
                  ref={typedRef}
                  className="wa-input"
                  placeholder="Type here and send..."
                  value={typedInput}
                  onChange={e => setTypedInput(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      sendTyped()
                    }
                  }}
                />
                <button className="wa-send" onClick={sendTyped} disabled={!typedInput.trim()}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/>
                    <path d="m21.854 2.147-10.94 10.939"/>
                  </svg>
                </button>
              </div>
            )}
            <div className="lc-ethics">Keeps listening during replies so you can interrupt naturally.</div>
          </div>

          <div className="livecall-log">
            {callLog.filter(m => m.role !== 'system').slice(-8).map(m => (
              <div key={m.id} className="lc-log-msg">
                <span className="lc-log-label">{m.role === 'user' ? 'You' : 'Twin'}</span>
                <span className="lc-log-text">{m.content.slice(0, 100)}{m.content.length > 100 ? '...' : ''}</span>
              </div>
            ))}
            <div ref={endRef} />
          </div>

          <div className="livecall-debug-toggle" onClick={() => setShowDebug(!showDebug)}>
            {showDebug ? '🔽 Hide Debug' : '▶ Show Debug'}
          </div>
          {showDebug && (
            <div className="livecall-debug">
              <div>Status: {callState} | Speak: {speaking ? '✅' : '❌'} | Proc: {processingRef.current ? '✅' : '❌'}</div>
              <div>Recognition: {getActiveState()} | Mode: {getTranscriberMode()}</div>
              <div className="debug-log">{debug.map((d, i) => <div key={i} className="debug-line"><span className="debug-t">{d.t}</span> {d.msg}</div>)}</div>
            </div>
          )}
        </div>

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
              <div className="livecall-note">Fast speech, short replies, and instant stop when you speak over the reply.</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
