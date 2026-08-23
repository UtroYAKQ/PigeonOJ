import { defineStore } from 'pinia'

import * as authApi from '@/api/auth'
import { TOKEN_STORAGE_KEY } from '@/api/http'
import * as usersApi from '@/api/users'
import type { GlobalRoleCode, ProfilePatch, User } from '@/types'
import { applyTheme } from '@/utils/theme'

function readToken(): string {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY) ?? ''
  } catch {
    return ''
  }
}

function persistToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_STORAGE_KEY, token)
  } catch {
    // localStorage 不可用时忽略（会话仅内存态）
  }
}

function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
  } catch {
    // 忽略
  }
}

/** 用户 store：登录态 / 当前用户 / 全局角色 / 主题偏好 */
export const useUserStore = defineStore('user', {
  state: () => ({
    token: readToken(),
    user: null as User | null,
    initialized: false,
  }),

  getters: {
    isLoggedIn: (state) => Boolean(state.token),
    /** 当前用户全局角色 code 列表 */
    roles: (state): GlobalRoleCode[] => state.user?.roles ?? [],
    isAdmin: (state) => (state.user?.roles ?? []).includes('admin'),
  },

  actions: {
    /** 应用启动时恢复会话：有 token 则拉取当前用户（路由守卫调用一次） */
    async init(): Promise<void> {
      if (this.initialized) return
      try {
        if (this.token) {
          this.user = await usersApi.getMe()
          applyTheme(this.user.theme)
        }
      } catch {
        // token 失效：清除本地会话
        this.token = ''
        this.user = null
        clearToken()
      } finally {
        this.initialized = true
      }
    },

    async login(email: string, password: string): Promise<void> {
      const res = await authApi.login(email, password)
      this.token = res.token
      this.user = res.user
      persistToken(res.token)
      applyTheme(res.user.theme)
      this.initialized = true
    },

    async logout(): Promise<void> {
      try {
        await authApi.logout()
      } catch {
        // 登出接口失败不阻断本地清理
      }
      this.token = ''
      this.user = null
      clearToken()
    },

    /** 更新资料（昵称 / 签名 / 头像 / 主题） */
    async updateProfile(patch: ProfilePatch): Promise<User> {
      this.user = await usersApi.updateMe(patch)
      if (patch.theme) applyTheme(patch.theme)
      return this.user
    },

    /** 注销账号（软注销，需密码确认） */
    async deactivate(password: string): Promise<void> {
      await usersApi.deleteMe(password)
      this.token = ''
      this.user = null
      clearToken()
    },

    hasRole(code: GlobalRoleCode): boolean {
      return this.roles.includes(code)
    },

    hasAnyRole(codes: string[]): boolean {
      return codes.some((c) => this.roles.includes(c as GlobalRoleCode))
    },
  },
})
