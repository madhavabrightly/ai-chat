/**
 * Detect avatar mood based on answer text and retrieved memories.
 */
export default function detectAvatarMood(answerText, retrievedMemories = []) {
  if (!retrievedMemories || retrievedMemories.length === 0) {
    if (!answerText) return 'calm'
    const t = answerText.toLowerCase()
    if (t.includes('proud') || t.includes('achieved') || t.includes('success')) return 'proud'
    if (t.includes('funny') || t.includes('joke') || t.includes('laughed') || t.includes('hilarious')) return 'funny'
    if (t.includes('kind') || t.includes('help') || t.includes('faith') || t.includes('generous')) return 'kind'
    if (t.includes('advice') || t.includes('wise') || t.includes('lesson') || t.includes('learn')) return 'thoughtful'
    return 'calm'
  }

  const topCat = retrievedMemories[0]?.category || ''
  const topEmotion = retrievedMemories[0]?.emotion || ''

  if (topCat === 'Humor') return 'funny'
  if (topCat === 'Career') return 'proud'
  if (topCat === 'Advice') return 'thoughtful'
  if (topCat === 'Faith & Kindness') return 'kind'
  if (topCat === 'Childhood' || topCat === 'Family') return 'happy'
  if (topEmotion === 'Joyful' || topEmotion === 'Heartwarming') return 'happy'
  if (topEmotion === 'Bittersweet' || topEmotion === 'Nostalgic') return 'thoughtful'

  if (answerText) {
    const t = answerText.toLowerCase()
    if (t.includes('proud') || t.includes('achieved')) return 'proud'
    if (t.includes('funny') || t.includes('joke') || t.includes('laughed')) return 'funny'
    if (t.includes('kind') || t.includes('help') || t.includes('faith')) return 'kind'
    if (t.includes('advice') || t.includes('wise') || t.includes('lesson')) return 'thoughtful'
  }

  return 'calm'
}
