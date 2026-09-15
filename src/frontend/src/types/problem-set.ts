/**
 * 题单模块类型（docs/contracts/problem-sets.md）。
 * 团队题单可见性与团队题目对齐：team_visible（全队可见）/ admin_visible（仅团队管理）。
 */

/** 题单可见性：全站 public/private；团队 team_visible/admin_visible */
export type ProblemSetVisibilityType = 'public' | 'private' | 'team_visible' | 'admin_visible'

/** 题单内题目项（题目元信息随行返回） */
export interface ProblemSetItem {
  problem_id: string
  title: string
  difficulty?: number | null
  /** 题目限制（与题库列表口径一致） */
  time_limit_ms?: number
  memory_limit_mb?: number
  /** 当前用户作答状态（登录请求回填）：true=已通过 / false=已尝试未通过 / null|缺省=未提交过（未登录恒缺省） */
  solved?: boolean | null
  sort_order: number
}

export interface ProblemSetSummary {
  id: string
  title: string
  description?: string | null
  visibility: ProblemSetVisibilityType
  status: 'active' | 'archived'
  owner_id: string
  /** 归属团队（非空 = 团队题单；题单中心 / mine 恒为空，管理视图区分来源用） */
  team_id?: string | null
  item_count: number
  /** 非空 = 经团队引用进入团队题单（引用时间；团队空间） */
  referenced_at?: string | null
  created_at: string
  updated_at: string
}

/** 题单详情：题目按 sort_order 展示（刷题不强制按序完成） */
export interface ProblemSetDetail extends ProblemSetSummary {
  items: ProblemSetItem[]
  can_manage: boolean
  /** 创建人昵称（详情页展示；列表不携带） */
  owner_name: string
}

export interface ProblemSetCreatePayload {
  title: string
  description?: string | null
  visibility?: 'public' | 'private'
}

/** 编辑题单元信息（缺省不动，传即改） */
export interface ProblemSetEditPayload {
  title?: string
  description?: string | null
  visibility?: 'public' | 'private'
}

/** 编排题目：全量替换题单内列表；同题单内 problem_id 不得重复 */
export interface ProblemSetItemsPayload {
  items: Array<{ problem_id: string; sort_order: number }>
}

export interface ProblemSetListQuery {
  page?: number
  page_size?: number
  keyword?: string
  /** 题单中心「我的」勾选：仅本人未下线题单（含私有；须登录） */
  mine?: boolean
}

/** 管理视图查询（来源筛选：solo=全站题单 / team=团队题单） */
export interface AdminProblemSetListQuery extends ProblemSetListQuery {
  status?: 'active' | 'archived'
  ownership?: 'solo' | 'team'
}
