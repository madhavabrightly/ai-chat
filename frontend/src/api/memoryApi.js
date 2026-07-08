const BASE = '' // same origin — works on localhost, tunnel, and any domain

export async function healthCheck() {
  const r = await fetch(BASE + '/health')
  if (!r.ok) throw new Error('Backend offline')
  return r.json()
}

export async function fetchComputeStatus() {
  const r = await fetch(BASE + '/compute-status')
  if (!r.ok) throw new Error('Compute status unavailable')
  return r.json()
}

export async function fetchMemories() {
  const r = await fetch(BASE + '/memories')
  if (!r.ok) throw new Error('Memories unavailable')
  return r.json()
}

export async function chatWithMemory(question) {
  const r = await fetch(BASE + '/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  if (!r.ok) throw new Error('Chat request failed')
  return r.json()
}
