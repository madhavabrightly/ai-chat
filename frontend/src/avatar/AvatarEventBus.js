export class AvatarEventBus {
  constructor() {
    this.listeners = new Map()
    this.lastSequence = 0
  }

  on(type, callback) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set())
    this.listeners.get(type).add(callback)
    return () => this.off(type, callback)
  }

  off(type, callback) {
    this.listeners.get(type)?.delete(callback)
  }

  emit(type, payload = {}) {
    const event = {
      type,
      sequence: ++this.lastSequence,
      at: performance.now(),
      ...payload,
    }
    for (const callback of this.listeners.get(type) || []) {
      try { callback(event) } catch {}
    }
    for (const callback of this.listeners.get('*') || []) {
      try { callback(event) } catch {}
    }
    return event
  }
}

export const avatarEventBus = new AvatarEventBus()
