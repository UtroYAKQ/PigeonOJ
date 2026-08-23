/**
 * 题库模块类型（docs/contracts/problems.md）。
 */

export type ProblemLanguage = 'python3.12' | 'cpp17' | 'java21'
export type ProblemDifficulty = 'easy' | 'medium' | 'hard'

export interface ProblemSummary {
  id: string
  title: string
  difficulty: ProblemDifficulty
  time_limit_ms: number
  memory_limit_mb: number
  spj: boolean
  status: string
  visibility?: string
  is_verified?: boolean
  created_at?: string
}

export interface ProblemSample { id?: string; name: string; input: string; output: string }
export interface ProblemTestCase {
  id: string
  name: string | null
  is_sample: boolean
  score: number
  sort_order: number
  input: string | null
  expected_output: string | null
}

/** 题目详情：test_cases / solution 仅管理角色返回（can_manage=true 时） */
export interface ProblemDetail extends ProblemSummary {
  description: string
  input_description?: string | null
  output_description?: string | null
  solution?: string | null
  owner_id: string
  samples: ProblemSample[]
  tags: string[]
  can_manage: boolean
  verified_at?: string | null
  published_at?: string | null
}

/** 测试点草稿：编辑器内编辑、整体替换提交（PUT /problems/:id/test-cases） */
export interface TestCaseDraft {
  name: string
  is_sample: boolean
  input: string
  expected_output: string
  score: number
  sort_order: number
}

export interface ProblemListQuery {
  page?: number
  page_size?: number
  difficulty?: string
  keyword?: string
  tag?: string
  /** mine = 我的题目管理视图（创建者看全部自己的题目；管理角色看可管理范围） */
  scope?: 'all' | 'mine'
  status?: 'draft' | 'published' | 'archived'
}

export interface ProblemEditPayload {
  title?: string
  description?: string
  input_description?: string | null
  output_description?: string | null
  solution?: string | null
  difficulty?: string
  visibility?: string
  time_limit_ms?: number
  memory_limit_mb?: number
  spj?: boolean
  spj_code?: string | null
}

export interface ProblemCreatePayload extends ProblemEditPayload {
  title: string
  description: string
}

/** 管理角色读取详情时返回测试点内容（含正式点回读，用于编辑） */
export interface ProblemDetailEx extends ProblemDetail {
  test_cases?: TestCaseDraft[] | null
}
