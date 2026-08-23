/**
 * API 请求统一入口：直接调用真实后端（docs/contracts/common.md 统一响应信封）。
 */
import { request as httpRequest } from './http'
import type { HttpMethod } from '@/types'

export async function apiRequest<T = unknown>(
  method: HttpMethod,
  path: string,
  data?: unknown,
): Promise<T> {
  return httpRequest<T>(path, {
    method,
    body: data === undefined ? undefined : JSON.stringify(data),
  })
}
