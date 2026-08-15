// 统一请求封装：处理后端 {code, message, data} 响应信封（见 docs/contracts/common.md）。
// code = 0 表示成功；非 0 抛 ApiError 并携带错误码 / 消息。
// 骨架阶段仅提供基础设施，不实现任何具体 API 调用。

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export interface Envelope<T = unknown> {
  code: number
  message: string
  data: T
}

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

export async function request<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  let resp: Response
  try {
    resp = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch {
    throw new ApiError(5000, '网络异常，请稍后重试')
  }

  let body: Envelope<T>
  try {
    body = (await resp.json()) as Envelope<T>
  } catch {
    throw new ApiError(resp.status, `服务响应异常（HTTP ${resp.status}）`, resp.status)
  }

  if (body.code !== 0) {
    throw new ApiError(body.code, body.message, resp.status)
  }
  return body.data
}

// 便捷方法（骨架阶段占位，业务调用方按需使用）
export const http = {
  get<T = unknown>(path: string) {
    return request<T>(path)
  },
  post<T = unknown>(path: string, data?: unknown) {
    return request<T>(path, { method: 'POST', body: JSON.stringify(data ?? {}) })
  },
  put<T = unknown>(path: string, data?: unknown) {
    return request<T>(path, { method: 'PUT', body: JSON.stringify(data ?? {}) })
  },
  delete<T = unknown>(path: string) {
    return request<T>(path, { method: 'DELETE' })
  },
}
