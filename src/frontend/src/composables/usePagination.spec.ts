import { describe, expect, it } from 'vitest'

import { usePagination } from './usePagination'

describe('usePagination', () => {
  it('翻页与改页容量：changeSize 回到第 1 页', () => {
    const { page, pageSize, changePage, changeSize, resetPage } = usePagination()
    changePage(5)
    expect(page.value).toBe(5)
    changeSize(50)
    expect(pageSize.value).toBe(50)
    expect(page.value).toBe(1)
    changePage(3)
    resetPage()
    expect(page.value).toBe(1)
  })

  it('竞态守卫：仅最新请求序号有效，过期响应应被丢弃', () => {
    // 复现「点末页（慢）→ 点首页（快）」：首页响应先回来，末页慢响应后到
    const { beginLoad, isCurrent } = usePagination()
    const staleSeq = beginLoad() // 末页慢请求
    const freshSeq = beginLoad() // 首页快请求
    expect(isCurrent(staleSeq)).toBe(false) // 末页响应后到 → 过期，丢弃
    expect(isCurrent(freshSeq)).toBe(true) // 首页响应有效
  })

  it('竞态守卫：无更新请求时当前响应始终有效', () => {
    const { beginLoad, isCurrent } = usePagination()
    const seq = beginLoad()
    expect(isCurrent(seq)).toBe(true)
    expect(isCurrent(seq + 999)).toBe(false)
  })
})
