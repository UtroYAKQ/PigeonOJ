/**
 * 组织模块类型（docs/contracts/orgs.md）。
 * 组织是多机构共用一个 OJ 的租户单元；组织角色经 user_roles（scope='org'）授权。
 */

/** 组织内我的角色：admin / member；非成员视图为 null */
export type OrgRoleType = 'admin' | 'member'
export type OrgStatusType = 'active' | 'disbanded'
export type OrgMemberStatusType = 'active' | 'removed'

export interface OrgSummary {
  id: string
  name: string
  description: string | null
  avatar_url: string | null
  created_at: string
  member_count: number
  team_count: number
  my_role: OrgRoleType | null
}

export interface OrgDetail extends OrgSummary {
  created_by: string
  status: OrgStatusType
  disbanded_at: string | null
}

export interface OrgMemberItem {
  user_id: string
  nickname: string
  avatar_url: string | null
  status: OrgMemberStatusType
  joined_at: string
  is_admin: boolean
  note: string | null
}

export interface OrgCreatePayload {
  name: string
  description?: string
  avatar_url?: string
  admin_user_ids?: string[]
}

export interface OrgUpdatePayload {
  name?: string
  description?: string
  avatar_url?: string
}

export interface OrgListQuery {
  page?: number
  page_size?: number
  keyword?: string
  status?: OrgStatusType
}

export interface OrgMemberListQuery {
  page?: number
  page_size?: number
  keyword?: string
  status?: OrgMemberStatusType
}

export interface OrgTeamListQuery {
  page?: number
  page_size?: number
  keyword?: string
  status?: 'active' | 'disbanded'
}

export interface OrgProblemListQuery {
  page?: number
  page_size?: number
  keyword?: string
  status?: 'draft' | 'published'
}