const RETRYABLE_STATUSES = new Set([401, 404, 405, 502, 503, 504])

function cleanBase(base) {
  return String(base || '').replace(/\/+$/, '')
}

function currentOrigin() {
  if (typeof window === 'undefined') return ''
  return window.location.origin
}

function devTunnelSwap(origin, fromPort, toPort) {
  if (!origin) return ''
  return origin
    .replace(`-${fromPort}.`, `-${toPort}.`)
    .replace(`:${fromPort}`, `:${toPort}`)
}

export function apiBaseCandidates() {
  const candidates = []
  const configured = typeof window !== 'undefined' ? window.__MEMORY_TWIN_API_BASE : ''
  const envBase = import.meta?.env?.VITE_API_BASE || ''
  const origin = currentOrigin()

  if (configured) candidates.push(cleanBase(configured))
  if (envBase) candidates.push(cleanBase(envBase))
  if (origin) candidates.push(origin)

  const backendGuess = devTunnelSwap(origin, '3090', '8000')
  if (backendGuess) candidates.push(backendGuess)

  const frontendGuess = devTunnelSwap(origin, '8000', '3090')
  if (frontendGuess && !origin.includes('-8000.')) candidates.push(frontendGuess)

  return [...new Set(candidates.map(cleanBase))]
}

export function apiUrl(path, base = '') {
  if (/^https?:\/\//i.test(path)) return path
  return `${cleanBase(base)}${path.startsWith('/') ? path : `/${path}`}`
}

export function shouldRetryApiStatus(status) {
  return RETRYABLE_STATUSES.has(status)
}
