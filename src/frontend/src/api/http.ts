// 统一请求封装（axios）：请求拦截器自动携带会话 Token，
// 响应拦截器处理后端 {code, message, data} 信封（见 docs/contracts/common.md）。
// code = 0 表示成功；非 0 抛 ApiError 并携带错误码 / 消息。

import axios, { AxiosError, type AxiosInstance } from 'axios'
import { i18n } from '@/i18n'
import type { Envelope } from '@/types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

/** 会话 Token 的本地存储 key（与 stores/user.ts 共用） */
export const TOKEN_STORAGE_KEY = 'pigeonoj.token'

export class ApiError extends Error {
  readonly code: number
  readonly httpStatus?: number

  constructor(code: number, message: string, httpStatus?: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.httpStatus = httpStatus
  }
}

function translate(key: string, params?: Record<string, unknown>): string {
  return (
    i18n as unknown as {
      global: { t: (key: string, params?: Record<string, unknown>) => string }
    }
  ).global.t(key, params)
}

function readLocale(): string {
  // legacy:false 模式下 global.locale 是 ref（zh-CN / en-US），与 i18n/index.ts 的 setLocale 同步
  const global = (i18n as unknown as { global: { locale: { value: string } } }).global
  return global.locale.value
}

function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

/** 信封体形状：code 必须为数值（docs/contracts/common.md） */
interface EnvelopeBody {
  code: number
  message?: string
  data?: unknown
}

function isEnvelopeBody(value: unknown): value is EnvelopeBody {
  return Boolean(value) && typeof value === 'object' && typeof (value as Envelope).code === 'number'
}

/** axios 实例：导出以便测试注入 adapter */
export const httpClient: AxiosInstance = axios.create({ baseURL: BASE_URL })

// 请求拦截器：自动携带 Bearer Token（localStorage 持久化，与 stores/user.ts 共用）；
// 同时携带 Accept-Language，后端据此返回对应语言的错误 message（docs/contracts/common.md）
httpClient.interceptors.request.use((config) => {
  const token = readToken()
  if (token && !config.headers.Authorization) {
    config.headers.Authorization = `Bearer ${token}`
  }
  config.headers['Accept-Language'] = readLocale()
  return config
})

httpClient.interceptors.response.use(
  (response) => {
    const body: unknown = response.data
    if (!isEnvelopeBody(body)) {
      throw new ApiError(
        response.status,
        translate('app.badResponse', { status: response.status }),
        response.status,
      )
    }
    if (body.code !== 0) {
      throw new ApiError(body.code, body.message ?? '', response.status)
    }
    // 解包信封：后续调用方直接拿到 data 字段
    response.data = body.data
    return response
  },
  (error: AxiosError) => {
    if (error instanceof ApiError) throw error
    if (!error.response) {
      // 网络层异常（超时 / 断网 / DNS 失败）
      throw new ApiError(5000, translate('app.networkError'))
    }
    const { status, data } = error.response
    // 后端错误响应仍为信封结构时优先透出业务错误码
    if (isEnvelopeBody(data)) {
      if (data.code !== 0) {
        throw new ApiError(data.code, data.message ?? '', status)
      }
      throw new ApiError(status, translate('app.badResponse', { status }), status)
    }
    throw new ApiError(status, translate('app.badResponse', { status }), status)
  },
)

export interface RequestOptions {
  method?: string
  /** 对象由 axios 自动 JSON 序列化；FormData 自动走 multipart（boundary 由浏览器生成） */
  body?: unknown
  headers?: Record<string, string>
}

export async function request<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const resp = await httpClient.request<T>({
    url: path,
    method: options.method ?? 'GET',
    data: options.body,
    headers: options.headers,
  })
  // 响应拦截器已校验 code=0 并解包信封
  return resp.data as T
}

/** multipart 上传统一入口：FormData 的 Content-Type 与 boundary 由 axios / 浏览器处理。 */
export function requestUpload<T = unknown>(path: string, data: FormData): Promise<T> {
  return request<T>(path, { method: 'POST', body: data })
}

/** 类型化 API 请求入口：对象 body 自动 JSON 序列化。 */
export function apiRequest<T = unknown>(method: string, path: string, data?: unknown): Promise<T> {
  return request<T>(path, { method, body: data })
}
