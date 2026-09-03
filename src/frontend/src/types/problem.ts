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
  /** 难度分（手动填写，类似 Codeforces；null/缺省 = 未评分） */
  difficulty?: number | null
  /** 通过率统计计数（problem_counters；排除 verify / system_error） */
  submission_count?: number
  accepted_count?: number
  /** 当前用户作答状态（登录请求回填）：true=已通过 / false=已尝试未通过 / null|缺省=未提交过（未登录恒缺省） */
  solved?: boolean | null
}

export interface ProblemSample {
  name: string
  input: string
  output: string
  /** 样例解释（Markdown；空字符串 = 无解释，不渲染解释区块） */
  explanation?: string
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

/** 题目详情（不含测试点——测试点走独立管理端点 GET /problems/:id/test-cases） */
export interface ProblemDetail extends ProblemSummary {
  /** 题目背景（必填；存量数据为「无」） */
  background: string
  description: string
  input_description?: string | null
  output_description?: string | null
  /** 题面说明（可选，Markdown，渲染于题面最后） */
  note?: string | null
  /** 官方题解：仅题目的管理者（admin 或创建者）返回 */
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
  samples_updated_at?: string | null
}

/** 测试点列表（独立管理端点 GET /problems/:id/test-cases；仅题目管理者可读） */
export interface ProblemTestCaseList {
  cases: ProblemTestCase[]
  updated_at?: string | null
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
  /** 题库中心「我的」勾选：仅本人已发布题目（任意可见性，含私有已发布；须登录） */
  mine?: boolean
  status?: 'draft' | 'published' | 'archived'
  /** 难度分闭区间筛选（未评分题目不落入任何区间） */
  difficulty_min?: number
  difficulty_max?: number
}

export interface ProblemEditPayload {
  title?: string
  background?: string | null
  description?: string
  input_description?: string | null
  output_description?: string | null
  /** 题面说明（Markdown；空字符串 = 清空，undefined = 不改动） */
  note?: string | null
  solution?: string | null
  /** 激活标签名（≤8；全量替换关联，undefined = 不改动） */
  tags?: string[]
  visibility?: string
  time_limit_ms?: number
  memory_limit_mb?: number
  /** 难度分（≥0；undefined = 不改动，沿用后端 ProblemUpdate 约定） */
  difficulty?: number | null
}

export interface ProblemCreatePayload extends ProblemEditPayload {
  title: string
  background: string
  description: string
  /** 题面要素必填（docs/contracts/problems.md） */
  input_description: string
  output_description: string
}
