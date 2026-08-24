import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, TOKEN_STORAGE_KEY, request } from './http'

/** 构造仅含 http.ts 所需字段的最小 Response 替身 */
function jsonResponse(status: number, body: unknown) {
  return { status, json: async () => body }
}

const fetchMock = vi.fn()

describe('api/http（统一响应信封处理）', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    localStorage.clear()
    fetchMock.mockReset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('code=0 时返回 data 字段', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { code: 0, message: 'ok', data: { id: 'u1' } }))
    const data = await request<{ id: string }>('/users/me')
    expect(data).toEqual({ id: 'u1' })
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/users/me', expect.any(Object))
  })

  it('业务错误：抛出携带 code / message / httpStatus 的 ApiError', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(409, { code: 3002, message: '提交状态冲突', data: null }))
    const err = await request('/submissions', { method: 'POST' }).catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).code).toBe(3002)
    expect((err as ApiError).message).toBe('提交状态冲突')
    expect((err as ApiError).httpStatus).toBe(409)
  })

  it('网络异常抛 code=5000 且提示已国际化', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('network down'))
    const err = await request('/problems').catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).code).toBe(5000)
    expect((err as ApiError).message).toContain('网络异常')
  })

  it('非 JSON 响应抛 badResponse 并携带 HTTP 状态码', async () => {
    fetchMock.mockResolvedValueOnce({ status: 502, json: async () => Promise.reject(new Error('not json')) })
    const err = await request('/problems').catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).message).toContain('502')
    expect((err as ApiError).httpStatus).toBe(502)
  })

  it('localStorage 存在 token 时附带 Authorization 头', async () => {
    localStorage.setItem(TOKEN_STORAGE_KEY, 'tok-123')
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { code: 0, message: 'ok', data: null }))
    await request('/submissions/1')
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer tok-123')
  })

  it('无 token 时不携带 Authorization 头，且 JSON 请求设置 Content-Type', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { code: 0, message: 'ok', data: null }))
    await request('/auth/login', { method: 'POST', body: '{}' })
    const headers = ((fetchMock.mock.calls[0] as unknown[])[1] as RequestInit)
      .headers as Record<string, string>
    expect(headers.Authorization).toBeUndefined()
    expect(headers['Content-Type']).toBe('application/json')
  })

  it('FormData 上传不覆盖 Content-Type（保留浏览器 boundary）', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { code: 0, message: 'ok', data: null }))
    const form = new FormData()
    form.append('file', new Blob(['x']), 'a.png')
    await request('/files/upload/avatar', { method: 'POST', body: form })
    const headers = ((fetchMock.mock.calls[0] as unknown[])[1] as RequestInit)
      .headers as Record<string, string>
    expect(headers['Content-Type']).toBeUndefined()
  })
})
