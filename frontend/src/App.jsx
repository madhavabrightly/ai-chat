import { useState, useEffect } from 'react'
import { healthCheck, fetchComputeStatus } from './api/memoryApi.js'
import StatusBadge from './components/StatusBadge.jsx'
import HomeScreen from './components/HomeScreen.jsx'
import ChatScreen from './components/ChatScreen.jsx'
import MemoryVault from './components/MemoryVault.jsx'

const NAV = [
  { id: 'home', label: 'Home', icon: '⌂' },
  { id: 'chat', label: 'Chat', icon: '✉' },
  { id: 'vault', label: 'Memories', icon: '◫' },
]

export default function App() {
  const [screen, setScreen] = useState('home')
  const [backendOnline, setBackendOnline] = useState(false)
  const [computeStatus, setComputeStatus] = useState(null)

  function refresh() {
    healthCheck().then(() => setBackendOnline(true)).catch(() => setBackendOnline(false))
    fetchComputeStatus().then(setComputeStatus).catch(() => setComputeStatus(null))
  }

  useEffect(() => { refresh() }, [])

  return (
    <div className="app">
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
          <HomeScreen
            onNavigate={setScreen}
            backendOnline={backendOnline}
            computeStatus={computeStatus}
            refreshStatus={refresh}
          />
        )}
        {screen === 'chat' && (
          <ChatScreen
            onNavigate={setScreen}
            backendOnline={backendOnline}
            computeStatus={computeStatus}
            refreshStatus={refresh}
          />
        )}
        {screen === 'vault' && (
          <MemoryVault
            onNavigate={setScreen}
            backendOnline={backendOnline}
          />
        )}
      </div>
    </div>
  )
}
