/**
 * Frontend avatar action plan — converts chat message + answer into mood/expression/gesture.
 */
import detectAvatarMood from './avatarMood.js'

export default function createAvatarActionPlan(userMessage, answer, retrievedMemories = []) {
  const mood = detectAvatarMood(answer, retrievedMemories)

  const expressionMap = {
    calm: 'gentle smile',
    happy: 'bright smile',
    thoughtful: 'soft eyes, slight frown',
    funny: 'grin, head tilt',
    kind: 'warm smile, soft gaze',
    proud: 'confident smile, nod',
    bored: 'gentle yawn',
  }

  const gestureMap = {
    calm: 'hands relaxed at side',
    happy: 'hands open, slight bounce',
    thoughtful: 'hand near chin',
    funny: 'hand wave, lean forward',
    kind: 'hand on heart',
    proud: 'hand on chest, stand tall',
    bored: 'head tilt, slow blink',
  }

  const actionMap = {
    funny: 'laugh softly, tilt head',
    proud: 'nod confidently, smile',
    thoughtful: 'gaze softly, pause',
    kind: 'lean in gently',
    bored: 'polite stretch',
    calm: 'breathe, blink gently',
  }

  const reasons = []
  if (retrievedMemories.length > 0) {
    const cat = retrievedMemories[0].category
    reasons.push(`based on "${cat}" memory`)
  } else {
    reasons.push('based on answer tone')
  }

  return {
    mood,
    expression: expressionMap[mood] || 'gentle smile',
    gesture: gestureMap[mood] || 'hands relaxed',
    recommendedAction: actionMap[mood] || 'gentle nod',
    reason: reasons.join(', '),
  }
}
