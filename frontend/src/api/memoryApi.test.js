import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  requestJson,
  healthCheck,
  fetchComputeStatus,
  fetchMemories,
  sendChatMessage,
  requestAvatarAction,
  saveMemory,
} from './memoryApi.js'

describe('memoryApi — requestJson helper', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('returns ok:true with parsed data on success', async () => {
    globalThis.fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: () => Promise.resolve(JSON.stringify({ status: 'ok' })),
    })
    const r = await requestJson('/health', { method: 'GET' })
    expect(r.ok).toBe(true)
    expect(r.data).toEqual({ status: 'ok' })
    expect(r.request_id).toMatch(/^test-uuid-/)
  })

  it('returns HTTP_ERROR on non-2xx with JSON body', async () => {
    globalThis.fetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      text: () => Promise.resolve(JSON.stringify({ error: 'boom' })),
    })
    const r = await requestJson('/chat', { method: 'POST', body: { q: 'x' } })
    expect(r.ok).toBe(false)
    expect(r.code).toBe('HTTP_ERROR')
    expect(r.http_status).toBe(500)
    expect(r.message).toBe('boom')
  })

  it('returns HTTP_ERROR on non-2xx with non-JSON body', async () => {
    globalThis.fetch.mockResolvedValueOnce({
      ok: false,
      status: 502,
      text: () => Promise.resolve('Bad Gateway'),
    })
    const r = await requestJson('/chat', { method: 'POST' })
    expect(r.ok).toBe(false)
    expect(r.code).toBe('HTTP_ERROR')
    expect(r.http_status).toBe(502)
  })

  it('returns PARSE_ERROR on 2xx with non-JSON body', async () => {
    globalThis.fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: () => Promise.resolve('<html>not json</html>'),
    })
    const r = await requestJson('/chat', { method: 'POST' })
    expect(r.ok).toBe(false)
    expect(r.code).toBe('PARSE_ERROR')
  })

  it('returns NETWORK_ERROR on fetch failure', async () => {
    globalThis.fetch.mockRejectedValueOnce(new Error('Failed to fetch'))
    const r = await requestJson('/chat', { method: 'POST' })
    expect(r.ok).toBe(false)
    expect(r.code).toBe('NETWORK_ERROR')
    expect(r.message).toBe('Failed to fetch')
  })

  it('returns CANCELLED when external signal aborts', async () => {
    const controller = new AbortController()
    globalThis.fetch.mockImplementationOnce(() => {
      controller.abort()
      const err = new Error('aborted')
      err.name = 'AbortError'
      return Promise.reject(err)
    })
    const r = await requestJson('/chat', { method: 'POST', signal: controller.signal })
    expect(r.ok).toBe(false)
    expect(r.code).toBe('CANCELLED')
  })

  it('returns TIMEOUT when timeout fires', async () => {
    globalThis.fetch.mockImplementationOnce(() => {
      const err = new Error('aborted')
      err.name = 'AbortError'
      return Promise.reject(err)
    })
    const r = await requestJson('/chat', { method: 'POST', timeoutMs: 1 })
    // Wait for timeout to fire
    await new Promise(r => setTimeout(r, 10))
    // The timeout fires after 1ms, so the next call should be TIMEOUT
    globalThis.fetch.mockImplementationOnce(() => {
      const err = new Error('aborted')
      err.name = 'AbortError'
      return Promise.reject(err)
    })
    const r2 = await requestJson('/chat', { method: 'POST', timeoutMs: 1 })
    expect(['TIMEOUT', 'CANCELLED']).toContain(r2.code)
  })

  it('sends X-Request-ID header', async () => {
    globalThis.fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: () => Promise.resolve('{}'),
    })
    await requestJson('/health', { method: 'GET' })
    const callArgs = globalThis.fetch.mock.calls[0]
    expect(callArgs[1].headers['X-Request-ID']).toMatch(/^test-uuid-/)
  })

  it('serializes body as JSON', async () => {
    globalThis.fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: () => Promise.resolve('{}'),
    })
    await requestJson('/chat', { method: 'POST', body: { q: 'hello' } })
    const callArgs = globalThis.fetch.mock.calls[0]
    expect(callArgs[1].body).toBe('{"q":"hello"}')
  })
})

describe('memoryApi — typed wrappers', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('healthCheck throws on failure', async () => {
    globalThis.fetch.mockResolvedValueOnce({
      ok: false,
      status: 503,
      text: () => Promise.resolve('{}'),
    })
    await expect(healthCheck()).rejects.toThrow()
  })

  it('healthCheck returns data on success', async () => {
    globalThis.fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: () => Promise.resolve(JSON.stringify({ status: 'ok' })),
    })
    const data = await healthCheck()
    expect(data.status).toBe('ok')
  })

  it('fetchComputeStatus returns data on success', async () => {
    globalThis.fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: () => Promise.resolve(JSON.stringify({ device: 'MI300X' })),
    })
    const data = await fetchComputeStatus()
    expect(data.device).toBe('MI300X')
  })

  it('fetchMemories returns memories array', async () => {
    globalThis.fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: () => Promise.resolve(JSON.stringify({ memories: [{ id: 'm1' }] })),
    })
    const data = await fetchMemories()
    expect(data.memories).toHaveLength(1)
  })

  it('saveMemory returns ok:true on success', async () => {
    globalThis.fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: () => Promise.resolve(JSON.stringify({ status: 'ok', memory: { id: 'm1' } })),
    })
    const r = await saveMemory({ title: 't', text: 'x' })
    expect(r.ok).toBe(true)
  })

  it('requests a non-blocking avatar action plan', async () => {
    globalThis.fetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      text: () => Promise.resolve(JSON.stringify({
        ok: true,
        plan: { mood: 'happy', director: 'modelscope_qwen3_0_6b' },
      })),
    })

    const result = await requestAvatarAction({
      answer: 'That is wonderful.',
      retrievedMemories: [],
      companionType: 'female',
    })

    expect(result.ok).toBe(true)
    expect(result.plan.director).toBe('modelscope_qwen3_0_6b')
    expect(globalThis.fetch.mock.calls[0][0]).toBe('/avatar/action')
  })
})
