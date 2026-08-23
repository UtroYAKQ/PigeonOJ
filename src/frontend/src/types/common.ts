/**
 * 通用类型：分页契约、API 响应信封、HTTP 方法。
 */

/** 分页契约（docs/contracts/common.md）：?page=1&page_size=20，page_size ≤ 100 */
export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

/** 后端统一响应信封 {code, message, data}（docs/contracts/common.md），code = 0 表示成功 */
export interface Envelope<T = unknown> {
  code: number
  message: string
  data: T
}

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'
