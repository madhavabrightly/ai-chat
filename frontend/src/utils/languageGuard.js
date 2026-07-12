/**
 * Frontend language guard — catches non-English characters in AI responses.
 * Safety net only — backend should filter first.
 */

const CHINESE_RE = /[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]/

export function containsChinese(text) {
  if (!text) return false
  return CHINESE_RE.test(text)
}

export function guardAnswer(text) {
  if (!containsChinese(text)) return text

  console.warn('[FRONTEND_LANGUAGE_GUARD] blocked_non_english_response')
  return "I found a memory, but the response mixed languages. Please ask again and I will answer in English."
}
