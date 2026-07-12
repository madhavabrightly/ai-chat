/**
 * Phase 1 Import Parser — parses WhatsApp TXT and JSON into per-message records.
 * Each message has: speaker, date, text, exact_source.
 * Also generates: summary, tone, emotions, chunks (for temp context).
 */

// WhatsApp line regexes (same as backend)
const WA1 = /^\[(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}[,\s]*\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?)\]\s+([^:]+?):\s*(.*)/
const WA2 = /^(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}[,\s]*\d{1,2}:\d{2}(?::\d{2})?(?:\s*AM|\s*PM)?)\s*[-–]\s*([^:]+?):\s*(.*)/
const WA3 = /^([A-Za-z][A-Za-z\s]+?):\s*(.*)/

function parseLine(line) {
  line = line.trim()
  if (!line) return null
  let m = WA1.exec(line)
  if (m) return { speaker: m[2].trim(), date: m[1].trim(), text: m[3].trim(), exact_source: line }
  m = WA2.exec(line)
  if (m) return { speaker: m[2].trim(), date: m[1].trim(), text: m[3].trim(), exact_source: line }
  m = WA3.exec(line)
  if (m) return { speaker: m[1].trim(), date: '', text: m[2].trim(), exact_source: line }
  return { speaker: '', date: '', text: line, exact_source: line }
}

function parseJSON(data) {
  let items = []
  if (Array.isArray(data)) items = data
  else if (data.messages) items = data.messages
  else if (data.memories) items = data.memories
  else items = [data]

  return items.map(item => {
    if (typeof item !== 'object') return { speaker: '', date: '', text: String(item), exact_source: String(item) }
    return {
      speaker: item.speaker || item.role || '',
      date: item.date || item.timestamp || item.datetime || '',
      text: item.text || item.content || item.message || JSON.stringify(item),
      exact_source: JSON.stringify(item, null, 0),
    }
  })
}

// ── Summary, tone, emotion detection ────────────────────────────────
function buildSummary(messages) {
  if (!messages.length) return 'Empty chat'
  const speakers = [...new Set(messages.slice(0, 50).map(m => m.speaker).filter(Boolean))]
  const speakerList = speakers.length ? speakers.slice(0, 5).join(', ') : 'unknown'
  const dates = messages.map(m => m.date).filter(Boolean)
  const dateRange = dates.length > 1 ? ` (${dates[0]} → ${dates[dates.length - 1]})` : ''
  return `${messages.length} messages from ${speakerList}${dateRange}`
}

function detectTone(messages) {
  if (!messages.length) return 'neutral'
  const text = messages.slice(0, 30).map(m => m.text).join(' ').toLowerCase()
  const warmWords = ['love', 'miss', 'dear', 'sweet', 'honey', 'beautiful', '❤️', '💕', '😊', '🥰']
  const playfulWords = ['haha', 'lol', '😂', '🤣', 'funny', 'joke']
  const seriousWords = ['important', 'serious', 'urgent', 'please', 'sorry']
  const warm = warmWords.filter(w => text.includes(w)).length
  const playful = playfulWords.filter(w => text.includes(w)).length
  const serious = seriousWords.filter(w => text.includes(w)).length
  if (warm >= playful && warm >= serious && warm > 0) return 'warm'
  if (playful > warm && playful > serious) return 'playful'
  if (serious > warm && serious > playful) return 'serious'
  return 'neutral'
}

function detectEmotions(messages) {
  if (!messages.length) return []
  const text = messages.slice(0, 30).map(m => m.text).join(' ').toLowerCase()
  const emotions = []
  if (/love|miss|❤️|💕|dear/.test(text)) emotions.push('love')
  if (/happy|glad|great|😊|🎉|awesome/.test(text)) emotions.push('joy')
  if (/sad|sorry|miss you|😢|cry/.test(text)) emotions.push('sadness')
  if (/angry|mad|furious|😠|hate/.test(text)) emotions.push('anger')
  if (/funny|haha|lol|😂|joke/.test(text)) emotions.push('humor')
  return emotions.length ? emotions : ['neutral']
}

// Build chunks for retrieval — group consecutive messages by speaker
function buildChunks(messages) {
  const chunks = []
  let currentGroup = []
  let currentSpeaker = null
  for (const msg of messages) {
    if (msg.speaker && msg.speaker === currentSpeaker && currentGroup.length < 5) {
      currentGroup.push(msg)
    } else {
      if (currentGroup.length > 0) {
        chunks.push({
          speaker: currentSpeaker || 'Unknown',
          text: currentGroup.map(m => m.text).join(' '),
          date: currentGroup[0].date || '',
          message_count: currentGroup.length,
          relevance: 0.5,
        })
      }
      currentGroup = [msg]
      currentSpeaker = msg.speaker
    }
  }
  if (currentGroup.length > 0) {
    chunks.push({
      speaker: currentSpeaker || 'Unknown',
      text: currentGroup.map(m => m.text).join(' '),
      date: currentGroup[0].date || '',
      message_count: currentGroup.length,
      relevance: 0.5,
    })
  }
  return chunks
}

export function parseImportFile(raw, filename) {
  const ext = filename.split('.').pop().toLowerCase()
  const messages = ext === 'json' ? parseJSON(JSON.parse(raw)) : raw.split('\n').map(parseLine).filter(Boolean)

  const parsed = messages.map((m, i) => ({
    id: `msg_${String(i + 1).padStart(4, '0')}`,
    speaker: m.speaker,
    date: m.date,
    text: m.text,
    exact_source: m.exact_source,
    emotion: 'neutral',
  }))

  return {
    file_name: filename,
    message_count: parsed.length,
    messages: parsed,
    summary: buildSummary(parsed),
    tone: detectTone(parsed),
    emotions: detectEmotions(parsed),
    chunks: buildChunks(parsed),
  }
}
