const FALLBACK_CLIP_HINTS = [
  'idle',
  'stand',
  'base',
  'show',
  'loop',
]

const ACTION_HINTS = {
  idle: ['idle', 'stand', 'base', 'show'],
  greeting: ['greet', 'hello', 'wave', 'show'],
  listening: ['listen', 'idle', 'stand', 'show'],
  thinking: ['think', 'idle', 'stand', 'show'],
  speaking: ['talk', 'speak', 'show', 'stand'],
  happy: ['happy', 'joy', 'show', 'stand'],
  proud: ['proud', 'show', 'stand'],
  thoughtful: ['think', 'idle', 'stand', 'show'],
  kind: ['kind', 'warm', 'idle', 'stand', 'show'],
  funny: ['laugh', 'fun', 'show', 'stand'],
  bored: ['bored', 'yawn', 'idle', 'stand', 'show'],
  error: ['idle', 'stand', 'show'],
}

const STATE_TO_ACTION = {
  door_opening: 'greeting',
  entering: 'greeting',
  greeting: 'greeting',
  listening: 'listening',
  user_speaking: 'listening',
  thinking: 'thinking',
  speaking: 'speaking',
  ai_speaking: 'speaking',
  interrupted: 'listening',
  idle: 'idle',
  calm: 'idle',
  happy: 'happy',
  proud: 'proud',
  thoughtful: 'thoughtful',
  kind: 'kind',
  funny: 'funny',
  bored: 'bored',
  error: 'error',
}

const MOOD_POSES = {
  calm: { energy: 0.24, headPitch: -0.01, headYaw: 0, lean: 0, expression: 'gentle_smile' },
  happy: { energy: 0.64, headPitch: -0.03, headYaw: 0.03, lean: 0.03, expression: 'bright_smile' },
  proud: { energy: 0.58, headPitch: -0.08, headYaw: -0.02, lean: -0.02, expression: 'confident_smile' },
  thoughtful: { energy: 0.34, headPitch: 0.06, headYaw: -0.06, lean: 0.02, expression: 'soft_frown' },
  kind: { energy: 0.42, headPitch: 0.02, headYaw: 0.04, lean: 0.04, expression: 'warm_smile' },
  funny: { energy: 0.7, headPitch: -0.02, headYaw: 0.08, lean: 0.06, expression: 'grin' },
  bored: { energy: 0.16, headPitch: 0.08, headYaw: -0.04, lean: -0.05, expression: 'tired' },
}

const STATE_POSES = {
  idle: { focus: 0.3, mouthBoost: 0, blinkRate: 1 },
  greeting: { focus: 0.75, mouthBoost: 0.05, blinkRate: 1.25 },
  listening: { focus: 0.9, mouthBoost: 0, blinkRate: 1.1, headPitch: 0.03 },
  thinking: { focus: 0.7, mouthBoost: 0, blinkRate: 0.85, headPitch: 0.08 },
  speaking: { focus: 0.95, mouthBoost: 0.2, blinkRate: 1.2 },
  error: { focus: 0.55, mouthBoost: 0, blinkRate: 1.4, headPitch: 0.05 },
}

function normalizeName(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim()
}

function clipNamesFromAnimations(animations = []) {
  return animations
    .map((clip, index) => clip?.name || `Animation ${index + 1}`)
    .filter(Boolean)
}

function findClip(clipNames, hints) {
  if (!clipNames.length) return null
  const normalized = clipNames.map(name => ({ name, normalized: normalizeName(name) }))
  for (const hint of hints) {
    const needle = normalizeName(hint)
    const found = normalized.find(clip => clip.normalized.includes(needle))
    if (found) return found.name
  }
  return null
}

export function buildAnimationRegistry(animations = []) {
  const clipNames = clipNamesFromAnimations(animations)
  const primaryClip = findClip(clipNames, FALLBACK_CLIP_HINTS) || clipNames[0] || null
  const actions = {}

  for (const [action, hints] of Object.entries(ACTION_HINTS)) {
    const clipName = findClip(clipNames, hints) || primaryClip
    actions[action] = {
      action,
      clipName,
      fallbackClip: Boolean(clipName && !findClip(clipNames, hints)),
      available: Boolean(clipName),
    }
  }

  return {
    clipNames,
    primaryClip,
    actions,
    hasClips: clipNames.length > 0,
    hasDedicatedClips: Object.values(actions).some(entry => !entry.fallbackClip),
  }
}

export function sanitizeActionPlan(plan = {}) {
  const safe = {}
  for (const key of ['mood', 'expression', 'gesture', 'movement', 'mouth_style', 'camera']) {
    const value = plan?.[key]
    if (typeof value === 'string' && value.length < 80) {
      safe[key] = value.replace(/[^\w -]/g, '').trim()
    }
  }
  if (Array.isArray(plan?.animation_cues)) {
    safe.animation_cues = plan.animation_cues
      .filter(cue => cue && typeof cue === 'object')
      .slice(0, 8)
      .map(cue => ({
        time: Number.isFinite(Number(cue.time)) ? Number(cue.time) : 0,
        action: String(cue.action || '').slice(0, 48),
        value: typeof cue.value === 'string' ? cue.value.slice(0, 80) : cue.value,
      }))
  }
  return safe
}

export function resolveAvatarAction({
  state = 'idle',
  mood = 'calm',
  isSpeaking = false,
  plan = null,
  registry,
} = {}) {
  const safePlan = sanitizeActionPlan(plan || {})
  const planMood = safePlan.mood || mood || 'calm'
  const actionKey = isSpeaking
    ? 'speaking'
    : STATE_TO_ACTION[state] || STATE_TO_ACTION[planMood] || 'idle'
  const registryEntry = registry?.actions?.[actionKey] || registry?.actions?.idle || null
  const moodPose = MOOD_POSES[planMood] || MOOD_POSES[mood] || MOOD_POSES.calm
  const statePose = STATE_POSES[actionKey] || STATE_POSES.idle

  return {
    action: actionKey,
    clipName: registryEntry?.clipName || registry?.primaryClip || null,
    fallbackClip: Boolean(registryEntry?.fallbackClip),
    mood: planMood,
    expression: safePlan.expression || moodPose.expression,
    gesture: safePlan.gesture || actionKey,
    movement: safePlan.movement || actionKey,
    mouthStyle: safePlan.mouth_style || (isSpeaking ? 'normal' : 'closed'),
    pose: {
      ...moodPose,
      ...statePose,
      energy: Math.max(moodPose.energy || 0, isSpeaking ? 0.55 : 0),
      mouthBoost: Math.max(statePose.mouthBoost || 0, isSpeaking ? 0.18 : 0),
    },
    cues: safePlan.animation_cues || [],
  }
}

export function actionFromEvent(event) {
  if (!event) return 'idle'
  if (event.type === 'speech.start') return 'listening'
  if (event.type === 'speech.final') return 'thinking'
  if (event.type === 'answer.first_token') return 'speaking'
  if (event.type === 'answer.completed') return 'idle'
  if (event.type === 'error') return 'error'
  return STATE_TO_ACTION[event.state] || 'idle'
}
