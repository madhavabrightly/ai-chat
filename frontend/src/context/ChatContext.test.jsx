import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { ChatProvider, useChat } from './ChatContext.jsx'

describe('ChatContext', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('starts with empty messages', () => {
    const { result } = renderHook(() => useChat(), { wrapper: ChatProvider })
    expect(result.current.messages).toEqual([])
  })

  it('addMessage adds a valid user message with generated id', () => {
    const { result } = renderHook(() => useChat(), { wrapper: ChatProvider })
    let id
    act(() => {
      id = result.current.addMessage('user', 'hello')
    })
    expect(id).toMatch(/^test-uuid-/)
    expect(result.current.messages).toHaveLength(1)
    expect(result.current.messages[0].role).toBe('user')
    expect(result.current.messages[0].content).toBe('hello')
  })

  it('addMessage rejects invalid role', () => {
    const { result } = renderHook(() => useChat(), { wrapper: ChatProvider })
    let id
    act(() => {
      id = result.current.addMessage('hacker', 'evil')
    })
    expect(id).toBeNull()
    expect(result.current.messages).toHaveLength(0)
  })

  it('updateMessage updates existing message by id', () => {
    const { result } = renderHook(() => useChat(), { wrapper: ChatProvider })
    let id
    act(() => {
      id = result.current.addMessage('user', 'hello')
    })
    act(() => {
      result.current.updateMessage(id, { content: 'updated' })
    })
    expect(result.current.messages[0].content).toBe('updated')
  })

  it('updateMessage is no-op for unknown id', () => {
    const { result } = renderHook(() => useChat(), { wrapper: ChatProvider })
    act(() => {
      result.current.addMessage('user', 'hello')
    })
    const before = result.current.messages[0].content
    act(() => {
      result.current.updateMessage('nonexistent', { content: 'x' })
    })
    expect(result.current.messages[0].content).toBe(before)
  })

  it('clearMessages removes all messages', () => {
    const { result } = renderHook(() => useChat(), { wrapper: ChatProvider })
    act(() => {
      result.current.addMessage('user', 'a')
      result.current.addMessage('assistant', 'b')
    })
    expect(result.current.messages).toHaveLength(2)
    act(() => {
      result.current.clearMessages()
    })
    expect(result.current.messages).toHaveLength(0)
  })

  it('persists messages to localStorage', () => {
    const { result } = renderHook(() => useChat(), { wrapper: ChatProvider })
    act(() => {
      result.current.addMessage('user', 'persist me')
    })
    const stored = JSON.parse(localStorage.getItem('memoryTwin.chatMessages'))
    expect(stored).toHaveLength(1)
    expect(stored[0].content).toBe('persist me')
  })

  it('loads messages from localStorage on mount', () => {
    localStorage.setItem('memoryTwin.chatMessages', JSON.stringify([
      { id: 'pre-1', role: 'user', content: 'from storage', status: 'complete' }
    ]))
    const { result } = renderHook(() => useChat(), { wrapper: ChatProvider })
    expect(result.current.messages).toHaveLength(1)
    expect(result.current.messages[0].content).toBe('from storage')
  })

  it('findMessageByRequestId returns matching message', () => {
    const { result } = renderHook(() => useChat(), { wrapper: ChatProvider })
    act(() => {
      result.current.addMessage('assistant', 'response', { request_id: 'req-abc' })
    })
    const found = result.current.findMessageByRequestId('req-abc')
    expect(found).toBeTruthy()
    expect(found.content).toBe('response')
  })

  it('findMessageByRequestId returns null for unknown id', () => {
    const { result } = renderHook(() => useChat(), { wrapper: ChatProvider })
    const found = result.current.findMessageByRequestId('nonexistent')
    expect(found).toBeNull()
  })

  it('preserves retry_payload on error messages', () => {
    const { result } = renderHook(() => useChat(), { wrapper: ChatProvider })
    act(() => {
      result.current.addMessage('user', 'retry me', {
        status: 'error',
        isError: true,
        retry_payload: {
          question: 'retry me',
          history: [],
        },
      })
    })
    expect(result.current.messages[0].retry_payload).toEqual({
      question: 'retry me',
      history: [],
    })
  })

  it('strips unknown fields from messages', () => {
    const { result } = renderHook(() => useChat(), { wrapper: ChatProvider })
    act(() => {
      result.current.addMessage('user', 'hello', { evil_field: 'should be stripped' })
    })
    const msg = result.current.messages[0]
    expect(msg.evil_field).toBeUndefined()
  })
})
