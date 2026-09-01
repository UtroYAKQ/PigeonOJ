/**
 * 题单模块类型（docs/contracts/problem-sets.md）。
 * 团队题单（visibility='team'）随 teams 模块开放，当前接口不接受。
 */

/** 题单内题目项（题目元信息随行返回） */
export interface ProblemSetItem {
  problem_id: string
  title: string
  difficulty?: number | null
  sort_order: number
}

export interface ProblemSetSummary {
  id: string
  title: string
  description?: string | null
  visibility: 'public' | 'private' | 'team'
  status: 'active' | 'archived'
  owner_id: string
  item_count: number
  created_at: string
  updated_at: string
}

/** 题单详情：题目按 sort_order 展示（刷题不强制按序完成） */
export interface ProblemSetDetail extends ProblemSetSummary {
  items: ProblemSetItem[]
  can_manage: boolean
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
}
