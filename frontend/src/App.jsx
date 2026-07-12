import { useState, useEffect, useRef } from 'react'
import { healthCheck, fetchComputeStatus } from './api/memoryApi.js'
import { ChatProvider } from './context/ChatContext.jsx'
import StatusBadge from './components/StatusBadge.jsx'
import HomeScreen from './components/HomeScreen.jsx'
import ChatScreen from './components/ChatScreen.jsx'
import LiveCallScreen from './components/LiveCallScreen.jsx'
import MemoryVault from './components/MemoryVault.jsx'
import MemoryAtlas from './components/MemoryAtlas.jsx'
import AMDProof from './components/AMDProof.jsx'
import HackathonDemo from './components/HackathonDemo.jsx'
import LiveAvatarPanel from './components/LiveAvatarPanel.jsx'
import detectAvatarMood from './utils/avatarMood.js'
import { speakText, stopSpeaking, loadBrowserVoices } from './utils/voiceEngine.js'

const NAV = [
  { id: 'home', label: 'Home', icon: '⌂' },
  { id: 'chat', label: 'Chat', icon: '✉' },
  { id: 'call', label: 'Live Call', icon: '📞' },
  { id: 'vault', label: 'Vault', icon: '◫' },
  { id: 'atlas', label: 'Atlas', icon: '🗺' },
  { id: 'amd', label: 'AMD Proof', icon: '🖥' },
  { id: 'demo', label: 'Demo', icon: '🎬' },
]

function AppContent() {
  const [screen, setScreen] = useState('chat')
  const [backendOnline, setBackendOnline] = useState(false)
  const [computeStatus, setComputeStatus] = useState(null)
  const [companion, setCompanion] = useState(() => localStorage.getItem('mt_companion') || null)
  const [avatarState, setAvatarState] = useState('idle')
  const [avatarMood, setAvatarMood] = useState('calm')
  const [lastAnswer, setLastAnswer] = useState('')
  const [lastUserMessage, setLastUserMessage] = useState('')
  const [lastRetrievedMemories, setLastRetrievedMemories] = useState([])
  const [muted, setMuted] = useState(false)
  // autoSpeak: when true, every chat answer is spoken aloud automatically.
  // Default OFF — the app is memory-based and fast; users can tap Replay to hear.
  const [autoSpeak, setAutoSpeak] = useState(() => {
    try { return localStorage.getItem('mt_auto_speak') === '1' } catch { return false }
  })
  const speechTimerRef = useRef(null)
  const currentTtsOpRef = useRef(null)

  // Load browser voices on mount
  useEffect(() => { loadBrowserVoices() }, [])

  function refresh() {
    healthCheck().then(() => setBackendOnline(true)).catch(() => setBackendOnline(false))
    fetchComputeStatus().then(setComputeStatus).catch(() => setComputeStatus(null))
  }

  useEffect(() => { refresh() }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (speechTimerRef.current) clearTimeout(speechTimerRef.current)
      if (currentTtsOpRef.current) {
        try { currentTtsOpRef.current.cancel() } catch {}
      }
      stopSpeaking()
    }
  }, [])

  function handleSelectCompanion(gender) {
    setCompanion(gender)
    localStorage.setItem('mt_companion', gender)
    setAvatarState('door_opening')
    setTimeout(() => setAvatarState('entering'), 1200)
    setTimeout(() => {
      setAvatarState('greeting')
      if (!muted) {
        const op = speakText('Hello, I am your Memory Twin companion. Ask me about a memory.', {
          companionType: gender,
          onEnd: () => { currentTtsOpRef.current = null },
          onCancel: () => { currentTtsOpRef.current = null },
          onError: () => { currentTtsOpRef.current = null },
        })
        currentTtsOpRef.current = op
      }
      speechTimerRef.current = setTimeout(() => setAvatarState('idle'), 3000)
    }, 2500)
  }

  function handleLastAnswer(answer, userMessage, retrievedMemories) {
    setLastAnswer(answer)
    setLastUserMessage(userMessage || '')
    setLastRetrievedMemories(retrievedMemories || [])

    // Cancel any previous TTS operation
    if (currentTtsOpRef.current) {
      try { currentTtsOpRef.current.cancel() } catch {}
      currentTtsOpRef.current = null
    }

    if (!answer) {
      setAvatarState('idle')
      return
    }

    setAvatarState('speaking')

    // Only auto-speak if user has explicitly enabled it (default OFF).
    // This keeps the app fast and quiet — users tap Replay to hear answers.
    if (!muted && autoSpeak) {
      const op = speakText(answer, {
        companionType: companion || 'female',
        onEnd: () => {
          currentTtsOpRef.current = null
          const mood = detectAvatarMood(answer, retrievedMemories || [])
          setAvatarMood(mood)
          setAvatarState(mood)
          speechTimerRef.current = setTimeout(() => setAvatarState('idle'), 3000)
        },
        onCancel: () => {
          currentTtsOpRef.current = null
          const mood = detectAvatarMood(answer, retrievedMemories || [])
          setAvatarMood(mood)
          setAvatarState(mood)
        },
        onError: () => {
          currentTtsOpRef.current = null
          const mood = detectAvatarMood(answer, retrievedMemories || [])
          setAvatarMood(mood)
          setAvatarState(mood)
          speechTimerRef.current = setTimeout(() => setAvatarState('idle'), 3000)
        },
      })
      currentTtsOpRef.current = op
    } else {
      const mood = detectAvatarMood(answer, retrievedMemories || [])
      setAvatarMood(mood)
      setAvatarState(mood)
      speechTimerRef.current = setTimeout(() => setAvatarState('idle'), 3000)
    }
  }

  // Derive engine status from computeStatus (no hardcoded values)
  const engineStatus = computeStatus ? {
    asr: computeStatus.asr || '—',
    retrieval: computeStatus.embedding || '—',
    reranker: computeStatus.reranker || '—',
    llm: computeStatus.llm || '—',
    tts: computeStatus.tts || '—',
    avatar: computeStatus.avatar_action || computeStatus.avatar || 'Procedural GLB',
  } : null

  return (
    <div className={`app app-3col app-screen-${screen}`}>
      <nav className="sidebar">
        <div className="sb-head">
          <span className="sb-logo">◆</span>
          <div>
            <div className="sb-title">Memory Twin</div>
            <div className="sb-track">Track 3</div>
          </div>
        </div>
        <div className="sb-nav">
          {NAV.map(n => (
            <button key={n.id} className={`sb-btn${screen === n.id ? ' sb-a' : ''}`} onClick={() => setScreen(n.id)}>
              <span className="sb-ico">{n.icon}</span>
              <span>{n.label}</span>
            </button>
          ))}
        </div>
        <div className="sb-foot">
          <StatusBadge online={backendOnline} />
        </div>
      </nav>

      <div className="main-area">
        {screen === 'home' && (
          <HomeScreen onNavigate={setScreen} backendOnline={backendOnline} computeStatus={computeStatus} refreshStatus={refresh} />
        )}
        {screen === 'chat' && (
          <ChatScreen
            onAvatarState={setAvatarState}
            onAvatarMood={setAvatarMood}
            onLastAnswer={handleLastAnswer}
            companion={companion}
          />
        )}
        {screen === 'call' && <LiveCallScreen />}
        {screen === 'vault' && <MemoryVault onNavigate={setScreen} backendOnline={backendOnline} />}
        {screen === 'atlas' && <MemoryAtlas />}
        {screen === 'amd' && <AMDProof />}
        {screen === 'demo' && <HackathonDemo onNavigate={setScreen} />}
      </div>

      {screen === 'chat' && (
        <LiveAvatarPanel
          avatarState={avatarState}
          avatarMood={avatarMood}
          companion={companion}
          onSelectCompanion={handleSelectCompanion}
          lastAnswer={lastAnswer}
          muted={muted}
          onMuteChange={setMuted}
          autoSpeak={autoSpeak}
          onAutoSpeakChange={(v) => {
            setAutoSpeak(v)
            try { localStorage.setItem('mt_auto_speak', v ? '1' : '0') } catch {}
          }}
          lastUserMessage={lastUserMessage}
          lastRetrievedMemories={lastRetrievedMemories}
          engineStatus={engineStatus}
        />
      )}

      {screen !== 'chat' && screen !== 'call' && companion && (
        <div className="avatar-float">
          <LiveAvatarPanel
            avatarState={avatarState}
            avatarMood={avatarMood}
            companion={companion}
            onSelectCompanion={handleSelectCompanion}
            lastAnswer={lastAnswer}
            muted={muted}
            onMuteChange={setMuted}
            autoSpeak={autoSpeak}
            onAutoSpeakChange={(v) => {
              setAutoSpeak(v)
              try { localStorage.setItem('mt_auto_speak', v ? '1' : '0') } catch {}
            }}
            lastUserMessage={lastUserMessage}
            lastRetrievedMemories={lastRetrievedMemories}
            engineStatus={engineStatus}
          />
        </div>
      )}
    </div>
  )
}

export default function App() {
  return (
    <ChatProvider>
      <AppContent />
    </ChatProvider>
  )
}
