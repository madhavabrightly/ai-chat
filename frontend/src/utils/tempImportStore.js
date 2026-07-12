/**
 * Temporary Import Store — sessionStorage for imported chat context.
 * Survives page navigation within the same browser session.
 * Clears when browser closes or user clicks "Clear".
 */
const KEYS = {
  data: 'memoryTwin.tempImportData',
  meta: 'memoryTwin.tempImportMeta',
}

export function getTempImportMeta() {
  try {
    const raw = sessionStorage.getItem(KEYS.meta)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}

export function getTempImportData() {
  try {
    const raw = sessionStorage.getItem(KEYS.data)
    return raw ? JSON.parse(raw) : []
  } catch { return [] }
}

export function setTempImport(meta, chunks) {
  try {
    sessionStorage.setItem(KEYS.meta, JSON.stringify(meta))
    sessionStorage.setItem(KEYS.data, JSON.stringify(chunks))
  } catch {}
}

export function clearTempImport() {
  try {
    sessionStorage.removeItem(KEYS.meta)
    sessionStorage.removeItem(KEYS.data)
  } catch {}
}

export function hasTempImport() {
  return !!getTempImportMeta()
}
