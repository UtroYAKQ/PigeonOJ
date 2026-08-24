// 统一请求封装：处理后端 {code, message, data} 响应信封（见 docs/contracts/common.md）。
// code = 0 表示成功；非 0 抛 ApiError 并携带错误码 / 消息。

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

function authHeaders(): Record<string, string> {
  try {
    const token = localStorage.getItem(TOKEN_STORAGE_KEY)
    return token ? { Authorization: `Bearer ${token}` } : {}
  } catch {
    return {}
  }
}

export async function request<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const isFormData = options.body instanceof FormData
  let resp: Response
  try {
    resp = await fetch(`${BASE_URL}${path}`, {
      headers: {
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        ...authHeaders(),
        ...(options.headers ?? {}),
      },
      ...options,
    })
  } catch {
    throw new ApiError(
      5000,
      (
        i18n as unknown as {
          global: { t: (key: string, params?: Record<string, unknown>) => string }
        }
      ).global.t('app.networkError'),
    )
  }

  let body: Envelope<T>
  try {
    body = (await resp.json()) as Envelope<T>
  } catch {
    throw new ApiError(
      resp.status,
      (
        i18n as unknown as {
          global: { t: (key: string, params?: Record<string, unknown>) => string }
        }
      ).global.t('app.badResponse', { status: resp.status }),
      resp.status,
    )
  }

  if (body.code !== 0) {
    throw new ApiError(body.code, body.message, resp.status)
  }
  return body.data
}

/** multipart 上传统一入口：保留浏览器自动生成的 FormData Content-Type boundary。 */
export async function requestUpload<T = unknown>(path: string, data: FormData): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body: data,
    headers: {},
  })
}
