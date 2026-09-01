import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  AxiosError,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'

import { ApiError, TOKEN_STORAGE_KEY, httpClient, request, requestUpload } from './http'

/** 成功信封 */
const envelope = (data: unknown = null) => ({ code: 0, message: 'ok', data })

/** 模拟浏览器 XHR 适配器：FormData 请求移除 Content-Type（boundary 由浏览器生成） */
function emulateXhrAdapter(config: InternalAxiosRequestConfig): void {
  if (config.data instanceof FormData) {
    config.headers.delete('Content-Type')
  }
}

function resolveOk(config: InternalAxiosRequestConfig, data: unknown = null): AxiosResponse {
  emulateXhrAdapter(config)
  return { status: 200, statusText: 'OK', headers: {}, data: envelope(data), config }
}

/** 构造 HTTP 错误：axios 默认 validateStatus 下非 2xx 走 rejected 分支 */
function rejectWithHttp(
  config: InternalAxiosRequestConfig,
  status: number,
  body: unknown,
): Promise<never> {
  emulateXhrAdapter(config)
  const response: AxiosResponse = { status, statusText: 'Error', headers: {}, data: body, config }
  return Promise.reject(new AxiosError('Request failed', undefined, config, {}, response))
}

const adapterMock = vi.fn()

describe('api/http（axios 统一响应信封处理）', () => {
  beforeEach(() => {
    localStorage.clear()
    adapterMock.mockReset()
    // 注入自定义 adapter：真实走完 axios 拦截器链（含自动携带 Token）
    httpClient.defaults.adapter = adapterMock as unknown as AxiosAdapter
    // 默认实现：200 + 成功信封
    adapterMock.mockImplementation(async (config: InternalAxiosRequestConfig) => resolveOk(config))
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('code=0 时返回解包后的 data 字段', async () => {
    adapterMock.mockImplementationOnce(async (config: InternalAxiosRequestConfig) =>
      resolveOk(config, { id: 'u1' }),
    )
    const data = await request<{ id: string }>('/users/me')
    expect(data).toEqual({ id: 'u1' })
    const [config] = adapterMock.mock.calls[0] as [InternalAxiosRequestConfig]
    expect(config.url).toBe('/users/me')
    expect(config.baseURL).toBe('/api/v1')
  })

  it('HTTP 200 但 code≠0：抛出携带 code / message / httpStatus 的 ApiError', async () => {
    adapterMock.mockImplementationOnce((config: InternalAxiosRequestConfig) =>
      Promise.resolve({
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
        data: { code: 3002, message: '提交状态冲突', data: null },
      }),
    )
    const err = await request('/submissions', { method: 'POST' }).catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).code).toBe(3002)
    expect((err as ApiError).message).toBe('提交状态冲突')
    expect((err as ApiError).httpStatus).toBe(200)
  })

  it('业务错误：HTTP 错误状态 + 信封体时透出业务错误码', async () => {
    adapterMock.mockImplementationOnce((config: InternalAxiosRequestConfig) =>
      rejectWithHttp(config, 409, { code: 3002, message: '提交状态冲突', data: null }),
    )
    const err = await request('/submissions', { method: 'POST' }).catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).code).toBe(3002)
    expect((err as ApiError).message).toBe('提交状态冲突')
    expect((err as ApiError).httpStatus).toBe(409)
  })

  it('网络异常抛 code=5000 且提示已国际化', async () => {
    adapterMock.mockImplementationOnce(async () => {
      throw new AxiosError('network down', AxiosError.ERR_NETWORK)
    })
    const err = await request('/problems').catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).code).toBe(5000)
    expect((err as ApiError).message).toContain('网络异常')
  })

  it('非 JSON 响应抛 badResponse 并携带 HTTP 状态码', async () => {
    adapterMock.mockImplementationOnce((config: InternalAxiosRequestConfig) =>
      rejectWithHttp(config, 502, '<html>Bad Gateway</html>'),
    )
    const err = await request('/problems').catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).message).toContain('502')
    expect((err as ApiError).httpStatus).toBe(502)
  })

  it('localStorage 存在 token 时请求拦截器自动附带 Authorization 头', async () => {
    localStorage.setItem(TOKEN_STORAGE_KEY, 'tok-123')
    await request('/submissions/1')
    const [config] = adapterMock.mock.calls[0] as [InternalAxiosRequestConfig]
    expect(config.headers.get('Authorization')).toBe('Bearer tok-123')
  })

  it('无 token 时不携带 Authorization 头，且 JSON 请求自动设置 Content-Type', async () => {
    await request('/auth/login', { method: 'POST', body: { email: 'a@b.c' } })
    const headers = (adapterMock.mock.calls[0] as [InternalAxiosRequestConfig])[0].headers
    expect(headers.get('Authorization')).toBeFalsy()
    expect(headers.get('Content-Type')).toContain('application/json')
  })

  it('FormData 上传不携带显式 Content-Type（boundary 由浏览器生成）', async () => {
    const form = new FormData()
    form.append('file', new Blob(['x']), 'a.png')
    await request('/files/upload/avatar', { method: 'POST', body: form })
    const headers = (adapterMock.mock.calls[0] as [InternalAxiosRequestConfig])[0].headers
    expect(headers.get('Content-Type')).toBeFalsy()
  })

  it('回归：requestUpload 携带 Authorization 头；显式 headers 与默认头合并而非二选一', async () => {
    localStorage.setItem(TOKEN_STORAGE_KEY, 'tok-upload')
    const form = new FormData()
    form.append('file', new Blob(['x']), 'a.png')
    await requestUpload('/files/upload/image', form)
    let headers = (adapterMock.mock.calls[0] as [InternalAxiosRequestConfig])[0].headers
    expect(headers.get('Authorization')).toBe('Bearer tok-upload')
    expect(headers.get('Content-Type')).toBeFalsy()

    await request('/export', { method: 'POST', headers: { Accept: 'text/csv' } })
    headers = (adapterMock.mock.calls[1] as [InternalAxiosRequestConfig])[0].headers
    expect(headers.get('Accept')).toBe('text/csv')
    expect(headers.get('Authorization')).toBe('Bearer tok-upload')
  })
})
