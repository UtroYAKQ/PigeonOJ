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

/* ==================== 团队空间（题库 / 题单 / 比赛，docs/contracts/teams.md 团队空间节） ==================== */

/** 团队题库列表项：题库摘要 + 引用来源字段 */
export interface TeamProblemSummary {
  id: string
  title: string
  time_limit_ms: number
  memory_limit_mb: number
  status: 'draft' | 'published' | 'archived'
  visibility: 'admin_visible' | 'team_visible'
  is_verified?: boolean
  /** 管理视图回填：存在待验证测试点，或样例晚于最近验题通过时间 */
  needs_reverification?: boolean
  created_at?: string
  difficulty?: number | null
  submission_count?: number
  accepted_count?: number
  solved?: boolean | null
  /** 非空 = 经团队引用进入团队题库（引用时间） */
  referenced_at?: string | null
}

/** 团队题库列表查询 */
export interface TeamProblemListQuery {
  page?: number
  page_size?: number
  keyword?: string
  status?: 'draft' | 'published' | 'archived'
  visibility?: 'admin_visible' | 'team_visible'
}

/** 引用题目进团队载荷 */
export interface TeamProblemReferencePayload {
  problem_id: string
  visibility: 'team_visible' | 'admin_visible'
}

/** 团队题单列表查询 */
export interface TeamSetListQuery {
  page?: number
  page_size?: number
  keyword?: string
  status?: 'active' | 'archived'
}

/** 创建团队题单载荷（copy_from_set_id 非空 = 复制本人全站题单条目，快照复制） */
export interface TeamSetCreatePayload {
  title: string
  description?: string | null
  copy_from_set_id?: string
}

/** 团队比赛列表查询 */
export interface TeamContestListQuery {
  page?: number
  page_size?: number
  keyword?: string
  status?: 'scheduled' | 'running' | 'finished'
}

/* ==================== 团队管理（admin 后台，docs/contracts/teams.md 管理端） ==================== */

/** 团队管理列表项（admin 全量，含已解散；带创建人昵称与状态） */
export interface TeamAdminSummary extends TeamSummary {
  status: 'active' | 'disbanded'
  creator_nickname: string | null
  /** 团队空间资源计数（题库 / 题单 / 比赛，全部状态） */
  problem_count: number
  problem_set_count: number
  contest_count: number
}

/** 团队管理详情（admin 免成员校验） */
export interface TeamAdminDetail extends TeamDetail {
  creator_nickname: string | null
  /** 团队空间资源计数（题库 / 题单 / 比赛，全部状态） */
  problem_count: number
  problem_set_count: number
  contest_count: number
}

/** 团队管理列表查询 */
export interface AdminTeamListQuery {
  page?: number
  page_size?: number
  keyword?: string
  status?: 'active' | 'disbanded'
}
