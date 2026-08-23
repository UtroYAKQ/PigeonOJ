/**
 * 用户中心 API（docs/contracts/users.md）：资料 / 注销 / 会话管理。
 * 数据所有权：所有查询均限定当前登录用户（后端按 user_id 约束）。
 */
import { apiRequest } from './request'
import type { User, UserSession } from './types'

export interface ProfilePatch {
  nickname?: string
  signature?: string | null
  avatar_url?: string | null
  theme?: 'light' | 'dark'
}

/** GET /users/me — 当前用户（auth） */
export function getMe() {
  return apiRequest<User>('GET', '/users/me')
}

/** PUT /users/me — 更新资料（auth） */
export function updateMe(patch: ProfilePatch) {
  return apiRequest<User>('PUT', '/users/me', patch)
}

/** DELETE /users/me — 注销账号（软注销，auth，需密码确认） */
export function deleteMe(password: string) {
  return apiRequest<null>('DELETE', '/users/me', { password })
}

/** GET /users/me/sessions — 会话列表（auth） */
export function listSessions() {
  return apiRequest<UserSession[]>('GET', '/users/me/sessions')
}

/** DELETE /users/me/sessions/:sid — 注销指定会话（owner） */
export function revokeSession(sessionId: string) {
  return apiRequest<null>('DELETE', `/users/me/sessions/${sessionId}`)
}
