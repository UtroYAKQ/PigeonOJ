/**
 * 组织模块类型（docs/contracts/orgs.md）。
 * 组织是多机构共用一个 OJ 的租户单元；组织角色经 user_roles（scope='org'）授权。
 */

/** 组织内我的角色（my_role）：org_admin / member；非成员视图为 null */
export type OrgRoleType = 'admin' | 'member'
/** 组织状态：active / disbanded 已解散（软解散） */
export type OrgStatusType = 'active' | 'disbanded'
/** 组织成员状态：active 在册 / removed 被移出 */
export type OrgMemberStatusType = 'active' | 'removed'

/** 组织列表项 / 摘要（my_role 为当前用户在该组织的角色，非成员视图为 null） */
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

/** 组织详情（成员可见；非成员 2003） */
export interface OrgDetail extends OrgSummary {
  created_by: string
  status: OrgStatusType
  disbanded_at: string | null
}

/** 组织成员列表项 */
export interface OrgMemberItem {
  user_id: string
  nickname: string
  avatar_url: string | null
  status: OrgMemberStatusType
  joined_at: string
  is_admin: boolean
  /** 成员备注：本人可备注自己，org_admin 可备注任意成员；无权限语义 */
  note: string | null
}

/** 创建组织载荷（admin；name 全站唯一，可同时任命初始组织管理员） */
export interface OrgCreatePayload {
  name: string
  description?: string
  avatar_url?: string
  admin_user_ids?: string[]
}

/** 编辑组织信息载荷（org_admin；缺省不动） */
export interface OrgUpdatePayload {
  name?: string
  description?: string
  avatar_url?: string
}

/** 我的组织列表查询 */
export interface OrgListQuery {
  page?: number
  page_size?: number
  keyword?: string
}

/** 组织成员列表查询（keyword 模糊昵称） */
export interface OrgMemberListQuery {
  page?: number
  page_size?: number
  keyword?: string
  status?: string
}

/** 组织名下团队列表查询 */
export interface OrgTeamListQuery {
  page?: number
  page_size?: number
  keyword?: string
  status?: string
}

/** 组织题库列表查询（缺省 published；status='draft' 草稿箱视图） */
export interface OrgProblemListQuery {
  page?: number
  page_size?: number
  keyword?: string
  status?: 'draft' | 'published'
}
