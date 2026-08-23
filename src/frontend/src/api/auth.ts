/**
 * 认证模块 API（docs/contracts/users.md）：注册 / 登录 / 登出 / 找回密码 / 换绑邮箱。
 */
import { apiRequest } from './request'
import type { LoginResult } from '@/types'

/** POST /auth/email-code — 发送邮箱验证码（public） */
export function sendEmailCode(email: string, purpose: string) {
  return apiRequest<{ hint?: string }>('POST', '/auth/email-code', { email, purpose })
}

/** POST /auth/register — 注册（public） */
export function register(data: { email: string; code: string; password: string; nickname: string }) {
  return apiRequest<null>('POST', '/auth/register', data)
}

/** POST /auth/login — 登录（public） */
export function login(email: string, password: string) {
  return apiRequest<LoginResult>('POST', '/auth/login', { email, password })
}

/** POST /auth/logout — 登出（auth） */
export function logout() {
  return apiRequest<null>('POST', '/auth/logout')
}

/** POST /auth/reset-password — 重置密码（public） */
export function resetPassword(data: { email: string; code: string; new_password: string }) {
  return apiRequest<null>('POST', '/auth/reset-password', data)
}

/** POST /auth/change-password — 修改密码（auth） */
export function changePassword(oldPassword: string, newPassword: string) {
  return apiRequest<null>('POST', '/auth/change-password', { old_password: oldPassword, new_password: newPassword })
}

/** POST /auth/change-email — 换绑邮箱（auth） */
export function changeEmail(newEmail: string, code: string) {
  return apiRequest<null>('POST', '/auth/change-email', { new_email: newEmail, code })
}
