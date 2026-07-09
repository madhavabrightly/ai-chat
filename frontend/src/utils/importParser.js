/**
 * Lightweight frontend import parser for TXT and JSON.
 * Chunks text, detects tone/emotions, returns preview.
 */
export function parseImportFile(raw, filename) {
  const ext = filename.split('.').pop().toLowerCase()
  const chunks = ext === 'json' ? parseJSON(raw) : parseTXT(raw)
  const allText = chunks.map(c => c.text).join('\n')
  const tone = detectTone(allText)
  const emotions = detectEmotions(allText)

  return {
    file_name: filename,
    summary: `${chunks.length} chunks extracted. Tone: ${tone}. Emotions: ${emotions.join(', ')}.`,
    tone,
    emotions,
    chunks,
  }
}

function parseTXT(raw) {
  const lines = raw.split('\n').map(l => l.trim()).filter(Boolean)
  const chunkSize = 15
  const chunks = []
  let current = []
  let exactLines = []

  for (const line of lines) {
    const match = line.match(/^(?:\[([^\]]+)\]\s*)?(?:([^:]+):\s*)?(.+)/)
    const timestamp = match?.[1] || ''
    const speaker = match?.[2] || ''
    const text = match?.[3] || line

    current.push(text)
    exactLines.push(line)

    if (current.length >= chunkSize) {
      chunks.push(makeChunk(current, exactLines, chunks.length, filename, speaker, timestamp))
      current = []
      exactLines = []
    }
  }
  if (current.length) {
    chunks.push(makeChunk(current, exactLines, chunks.length, filename, '', ''))
  }
  return chunks.length ? chunks : [{ ...makeChunk([raw], [raw], 0, filename, '', ''), text: raw.slice(0, 800), exact_source: raw.slice(0, 800) }]
}

function parseJSON(raw) {
  let data
  try { data = JSON.parse(raw) } catch { return [{ temp_id: 'err_001', text: 'Invalid JSON file.', exact_source: '', speaker: '', timestamp: '', emotion: 'error', tags: ['error'], temporary: true }] }

  let texts = []
  if (Array.isArray(data)) {
    texts = data.map(item => {
      const t = item.text || item.content || JSON.stringify(item)
      return `[${item.speaker || ''}] ${t}`
    })
  } else if (data.messages) {
    texts = data.messages.map(m => `[${m.speaker || m.role || 'Unknown'}] ${m.text || m.content || ''}`)
  } else if (data.memories) {
    texts = data.memories.map(m => m.text || m.content || '')
  }

  const chunks = []
  const chunkSize = 10
  for (let i = 0; i < texts.length; i += chunkSize) {
    const slice = texts.slice(i, i + chunkSize)
    chunks.push({
      temp_id: `temp_${String(chunks.length + 1).padStart(3, '0')}`,
      source_file: filename,
      speaker: '',
      timestamp: '',
      text: slice.join('\n').slice(0, 800),
      exact_source: slice.join('\n'),
      emotion: 'neutral',
      tags: ['imported-json'],
      temporary: true,
    })
  }
  return chunks.length ? chunks : [{ temp_id: 'temp_001', source_file: filename, speaker: '', timestamp: '', text: raw.slice(0, 800), exact_source: raw.slice(0, 800), emotion: 'neutral', tags: ['imported'], temporary: true }]
}

function makeChunk(texts, exactLines, idx, filename, speaker, timestamp) {
  return {
    temp_id: `temp_${String(idx + 1).padStart(3, '0')}`,
    source_file: filename,
    speaker,
    timestamp,
    text: texts.join('\n').slice(0, 800),
    exact_source: exactLines.join('\n'),
    emotion: 'neutral',
    tags: ['imported', speaker ? `speaker:${speaker}` : ''].filter(Boolean),
    temporary: true,
  }
}

function detectTone(text) {
  const t = text.toLowerCase()
  const scores = {
    warm: (t.match(/warm|kind|gentle|care|hug|comfort|peace/g) || []).length,
    playful: (t.match(/funny|joke|hilarious|laugh|witty|😂|😆/g) || []).length,
    caring: (t.match(/love|dear|sweet|miss|hope|feel/g) || []).length,
    serious: (t.match(/important|must|serious|need|responsibility/g) || []).length,
    emotional: (t.match(/sad|cry|hurt|regret|sorry|happy|joy|grateful/g) || []).length,
  }
  return Object.entries(scores).sort((a, b) => b[1] - a[1])[0]?.[0] || 'neutral'
}

function detectEmotions(text) {
  const t = text.toLowerCase()
  const emotions = []
  if (/happy|joy|delighted|grateful/.test(t)) emotions.push('joyful')
  if (/sad|cry|miss|lonely|regret/.test(t)) emotions.push('nostalgic')
  if (/love|adore|dear|sweet/.test(t)) emotions.push('loving')
  if (/funny|joke|laugh|hilarious/.test(t)) emotions.push('amused')
  if (/warm|kind|gentle|cozy/.test(t)) emotions.push('warm')
  return emotions.length ? emotions : ['neutral']
}
