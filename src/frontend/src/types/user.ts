/**
 * 用户模块类型（docs/contracts/users.md）。
 */

export type UserStatus = 'active' | 'frozen' | 'banned' | 'deleted'

/** 全局角色 code（docs/security.md） */
export type GlobalRoleCode = 'admin' | 'tutor' | 'user'

export interface RoleInfo {
  code: GlobalRoleCode
  name: string
  description: string
}

export interface User {
  id: string
  email: string
  email_verified: boolean
  nickname: string
  avatar_url: string | null
  signature: string | null
  theme: string // 'light' | 'dark'
  status: UserStatus
  last_login_at: string | null
  created_at: string
  updated_at: string
  /** 当前用户的全局角色（管理列表接口按 user_roles 附加；个人接口返回自身角色） */
  roles?: GlobalRoleCode[]
}

export interface UserSession {
  id: string
  device_info: string | null
  ip_address: string | null
  /** 登录地（ip2region 离线解析：「中国 北京 北京市 移动」；内网「内网IP」；null=解析失败） */
  location: string | null
  user_agent: string | null
  expires_at: string
  revoked_at: string | null
  last_active_at: string | null
  created_at: string
  /** 是否为当前登录会话（仅本人会话列表返回） */
  current?: boolean
}

export interface LoginResult {
  token: string
  user: User
}

/** 更新个人资料载荷（PUT /users/me） */
export interface ProfilePatch {
  nickname?: string
  signature?: string | null
  avatar_url?: string | null
  theme?: 'light' | 'dark'
}
