import { afterEach, describe, expect, it, vi } from 'vitest'

import { goBackOrFallback } from './navigation'

type HistoryState = { back?: string | null } | null

const originalState = window.history.state

function setState(state: HistoryState) {
  Object.defineProperty(window.history, 'state', {
    configurable: true,
    get: () => state,
  })
}

function mockRouter() {
  return { back: vi.fn(), push: vi.fn().mockResolvedValue(undefined) }
}

afterEach(() => {
  Object.defineProperty(window.history, 'state', {
    configurable: true,
    value: originalState,
  })
})

describe('goBackOrFallback', () => {
  it('存在 SPA 内上一跳（back 非空）时执行 router.back()', () => {
    setState({ back: '/admin/problems' })
    const router = mockRouter()
    goBackOrFallback(router as never, '/admin/problems')
    expect(router.back).toHaveBeenCalledTimes(1)
    expect(router.push).not.toHaveBeenCalled()
  })

  it('直达 URL（state 为 null）时落兜底路径', () => {
    setState(null)
    const router = mockRouter()
    goBackOrFallback(router as never, '/admin/problems')
    expect(router.push).toHaveBeenCalledWith('/admin/problems')
    expect(router.back).not.toHaveBeenCalled()
  })

  it('back 为 null（无上一跳）时落兜底路径', () => {
    setState({ back: null })
    const router = mockRouter()
    goBackOrFallback(router as never, '/admin/problems')
    expect(router.push).toHaveBeenCalledWith('/admin/problems')
    expect(router.back).not.toHaveBeenCalled()
  })
})
