/**
 * Detect if user is trying to save a memory.
 */
const TRIGGERS = [
  'remember that',
  'save this',
  'my favorite',
  'i like ',
  'i dislike ',
  'i love ',
  'i hate ',
  'i believe ',
  'my goal',
  'my dream',
  'important to me',
  'never forget',
  'always remember',
  'this is why',
]

export default function detectMemoryIntent(text) {
  if (!text) return { shouldSave: false }
  const lower = text.toLowerCase()

  const matched = TRIGGERS.find(t => lower.includes(t))
  if (!matched) return { shouldSave: false }

  // Try to extract a title
  let title = 'Personal Memory'
  if (lower.includes('my favorite')) {
    title = 'Favorite Thing'
  } else if (lower.includes('i believe')) {
    title = 'Personal Belief'
  } else if (lower.includes('my goal') || lower.includes('my dream')) {
    title = 'Life Goal'
  } else if (lower.includes('important to me')) {
    title = 'Important Memory'
  } else if (lower.includes('i like ') || lower.includes('i love ')) {
    title = 'Something I Like'
  } else if (lower.includes('i dislike ') || lower.includes('i hate ')) {
    title = 'Something I Dislike'
  }

  // Detect category from content
  let category = 'Personal'
  if (lower.includes('family') || lower.includes('mom') || lower.includes('dad') || lower.includes('grandma')) {
    category = 'Family'
  } else if (lower.includes('work') || lower.includes('job') || lower.includes('career') || lower.includes('promotion')) {
    category = 'Career'
  } else if (lower.includes('childhood') || lower.includes('kid') || lower.includes('grew up') || lower.includes('school')) {
    category = 'Childhood'
  } else if (lower.includes('advice') || lower.includes('wise') || lower.includes('lesson')) {
    category = 'Advice'
  } else if (lower.includes('faith') || lower.includes('god') || lower.includes('believe') || lower.includes('kind')) {
    category = 'Faith & Kindness'
  } else if (lower.includes('funny') || lower.includes('joke') || lower.includes('hilarious')) {
    category = 'Humor'
  }

  // Detect emotion
  let emotion = 'Neutral'
  if (lower.includes('love') || lower.includes('happy') || lower.includes('joy') || lower.includes('wonderful')) {
    emotion = 'Joyful'
  } else if (lower.includes('sad') || lower.includes('miss') || lower.includes('nostalgic')) {
    emotion = 'Nostalgic'
  } else if (lower.includes('angry') || lower.includes('hate') || lower.includes('annoy')) {
    emotion = 'Bittersweet'
  } else if (lower.includes('grateful') || lower.includes('thankful') || lower.includes('blessed')) {
    emotion = 'Heartwarming'
  } else if (lower.includes('funny') || lower.includes('laugh')) {
    emotion = 'Amused'
  }

  const words = text.split(' ')
  const relevantWords = words.filter(w => w.length > 3 && !['that', 'this', 'with', 'from', 'have', 'been', 'were'].includes(w.toLowerCase()))
  const tags = [...new Set([...relevantWords.slice(0, 4).map(w => w.toLowerCase().replace(/[^a-z]/g, '')), category.toLowerCase()])].filter(Boolean)

  return {
    shouldSave: true,
    title,
    category,
    emotion,
    tags,
    text,
  }
}
