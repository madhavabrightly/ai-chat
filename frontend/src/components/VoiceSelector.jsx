import { useState, useEffect } from 'react'
import { getAvailableVoices, onVoicesReady } from '../utils/voiceEngine.js'

const STORAGE_MALE = 'memoryTwin.preferredMaleVoice'
const STORAGE_FEMALE = 'memoryTwin.preferredFemaleVoice'

export default function VoiceSelector({ companionType }) {
  const [voices, setVoices] = useState([])
  const [selectedName, setSelectedName] = useState('')

  useEffect(() => {
    onVoicesReady(list => {
      setVoices(list)
      const key = companionType === 'male' ? STORAGE_MALE : STORAGE_FEMALE
      const saved = localStorage.getItem(key)
      if (saved && list.find(v => v.name === saved)) {
        setSelectedName(saved)
      } else if (!saved) {
        setSelectedName('')
      }
    })
  }, [companionType])

  function handleChange(name) {
    setSelectedName(name)
    const key = companionType === 'male' ? STORAGE_MALE : STORAGE_FEMALE
    localStorage.setItem(key, name)
  }

  if (voices.length === 0) return null

  return (
    <div className="voice-selector">
      <select
        className="voice-select"
        value={selectedName}
        onChange={e => handleChange(e.target.value)}
      >
        <option value="">Auto-detect {companionType === 'male' ? 'male' : 'female'} voice</option>
        {voices.map(v => (
          <option key={v.name} value={v.name}>
            {v.name} ({v.lang})
          </option>
        ))}
      </select>
    </div>
  )
}
