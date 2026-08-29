/**
 * 题库模块类型（docs/contracts/problems.md）。
 */

export type ProblemLanguage = 'python3.12' | 'cpp17' | 'java21'

/** 标签（GET /problems/tags 公开激活列表；/admin/tags 管理全量） */
export interface ProblemTagItem {
  id: string
  name: string
  color?: string | null
  status?: 'active' | 'archived'
  created_at?: string
}

export interface ProblemSummary {
  id: string
  title: string
  time_limit_ms: number
  memory_limit_mb: number
  status: string
  visibility?: string
  is_verified?: boolean
  /** scope=mine 管理视图返回：未验题或案例晚于最近验题通过时间变更 */
  needs_reverification?: boolean
  created_at?: string
}

export interface ProblemSample {
  name: string
  input: string
  output: string
}
export interface ProblemTestCase {
  id: string
  name: string | null
  sort_order: number
  input: string | null
  expected_output: string | null
  /** true = 当前为暂存目标状态（改动未验题晋升） */
  staged?: boolean
}

/** 题目详情：test_cases / solution 仅管理角色返回（can_manage=true 时） */
export interface ProblemDetail extends ProblemSummary {
  /** 题目背景（必填；存量数据为「无」） */
  background: string
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
  /** 发布门禁：未验题 / 测试点或样例晚于最近验题通过时间变更须重验 */
  needs_reverification?: boolean
  /** 测试点集合状态缓存：empty / to_verify / to_reverify / ok */
  case_status?: string | null
  cases_updated_at?: string | null
  samples_updated_at?: string | null
}

/** 测试点草稿：编辑器内编辑；id 存在表示服务器已有该测试点（保存时按行 diff 增量提交） */
export interface TestCaseDraft {
  id?: string
  name: string
  input: string
  expected_output: string
  sort_order: number
  /** 暂存目标状态标记（服务器返回；保存后按响应重置） */
  staged?: boolean
}

/**
 * 增量更新测试点载荷（PATCH /problems/:id/test-cases）；id=null 表示新增。
 * input/expected_output 传字符串则整体替换该侧内容（空字符串 = 清空）；
 * 前端编辑器始终提交完整内容，清空的文本框以 "" 提交
 */
export interface TestCaseUpsertPayload {
  id?: string | null
  name: string
  input: string
  expected_output: string
  sort_order: number
}

export interface ProblemListQuery {
  page?: number
  page_size?: number
  keyword?: string
  tag?: string
  /** mine = 我的题目管理视图（创建者看全部自己的题目；管理角色看可管理范围） */
  scope?: 'all' | 'mine'
  status?: 'draft' | 'published' | 'archived'
}

export interface ProblemEditPayload {
  title?: string
  background?: string | null
  description?: string
  input_description?: string | null
  output_description?: string | null
  solution?: string | null
  /** 激活标签名（≤8；全量替换关联，undefined = 不改动） */
  tags?: string[]
  visibility?: string
  time_limit_ms?: number
  memory_limit_mb?: number
}

export interface ProblemCreatePayload extends ProblemEditPayload {
  title: string
  background: string
  description: string
  /** 题面要素必填（docs/contracts/problems.md） */
  input_description: string
  output_description: string
}

/** 管理角色读取详情时返回测试点内容（含正式点回读，用于编辑） */
export interface ProblemDetailEx extends ProblemDetail {
  test_cases?: ProblemTestCase[] | null
}
