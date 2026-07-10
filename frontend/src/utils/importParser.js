/**
 * Phase 1 Import Parser — parses WhatsApp TXT and JSON into per-message records.
 * Each message has: speaker, date, text, exact_source.
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

export function parseImportFile(raw, filename) {
  const ext = filename.split('.').pop().toLowerCase()
  const messages = ext === 'json' ? parseJSON(JSON.parse(raw)) : raw.split('\n').map(parseLine).filter(Boolean)

  return {
    file_name: filename,
    message_count: messages.length,
    messages: messages.map((m, i) => ({
      id: `msg_${String(i + 1).padStart(4, '0')}`,
      speaker: m.speaker,
      date: m.date,
      text: m.text,
      exact_source: m.exact_source,
      emotion: 'neutral',
    })),
  }
}
