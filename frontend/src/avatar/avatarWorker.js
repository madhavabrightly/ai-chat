import { sanitizeActionPlan } from './AnimationRegistry.js'

function normalizePlannerMessage(message) {
  const plan = sanitizeActionPlan(message?.plan || {})
  return {
    id: message?.id || `avatar_plan_${Date.now()}`,
    ok: true,
    plan,
  }
}

self.onmessage = (event) => {
  try {
    self.postMessage(normalizePlannerMessage(event.data || {}))
  } catch (error) {
    self.postMessage({
      id: event.data?.id || null,
      ok: false,
      error: error?.message || 'Avatar planner worker failed',
    })
  }
}
