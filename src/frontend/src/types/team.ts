/**
 * 团队模块类型（docs/contracts/teams.md）。
 */

export type TeamRoleType = 'creator' | 'admin' | 'member'
export type TeamMemberStatusType = 'active' | 'exited' | 'kicked'
export type TeamApplicationStatusType = 'pending' | 'approved' | 'rejected'

/** 团队列表项 / 摘要（my_role 为当前用户在该团队的角色，非成员视图为 null） */
export interface TeamSummary {
  id: string
  name: string
  description: string | null
  avatar_url: string | null
  created_at: string
  member_count: number
  my_role: TeamRoleType | null
}

/** 团队详情（成员可见） */
export interface TeamDetail extends TeamSummary {
  creator_id: string
  status: 'active' | 'disbanded'
  disbanded_at: string | null
}

/** 成员列表项 */
export interface TeamMemberItem {
  user_id: string
  nickname: string
  avatar_url: string | null
  status: TeamMemberStatusType
  joined_at: string
  is_creator: boolean
  is_admin: boolean
}

/** 加入申请列表项 */
export interface TeamApplicationItem {
  id: string
  team_id: string
  user_id: string
  nickname: string
  invite_token: string | null
  status: TeamApplicationStatusType
  applied_at: string
  reviewed_by: string | null
  reviewed_at: string | null
}

/** 邀请链接创建响应（token 存 Redis，可多人使用、不可撤销） */
export interface TeamInviteCreated {
  token: string
  expires_at: string
}

/** 邀请链接解析响应（public 落地页） */
export interface TeamInviteResolved {
  team_id: string
  team_name: string
  expires_at: string
}

/** 创建 / 编辑团队载荷 */
export interface TeamUpsertPayload {
  name: string
  description?: string
  avatar_url?: string
}
