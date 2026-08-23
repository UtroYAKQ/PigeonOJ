/**
 * 前端共享类型：与 docs/contracts/ 各模块契约的数据结构对齐。
 * 后端响应统一信封 {code, message, data}（见 common.md），此处类型均为信封内 data 的形状。
 */

/** 分页契约（docs/contracts/common.md）：?page=1&page_size=20，page_size ≤ 100 */
export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

// ---------------- 用户模块（docs/contracts/users.md） ----------------

export type UserStatus = 'active' | 'frozen' | 'banned' | 'deleted'

/** 全局角色 code（docs/architecture.md 权限设计） */
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

// ---------------- 题库 / 判题模块（docs/contracts/problems.md、judge.md） ----------------
export type ProblemLanguage = 'python3.12' | 'cpp17' | 'java21'
export type ProblemDifficulty = 'easy' | 'medium' | 'hard'
export type SubmissionStatus = 'pending' | 'judging' | 'accepted' | 'wrong_answer' | 'time_limit_exceeded' | 'memory_limit_exceeded' | 'output_limit_exceeded' | 'runtime_error' | 'compile_error' | 'system_error'

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

export interface TestCaseDraft {
  name: string
  is_sample: boolean
  input: string
  expected_output: string
  score: number
  sort_order: number
}

export interface Submission {
  id: string
  problem_id?: string
  language?: string
  submit_type?: string
  code?: string
  status: SubmissionStatus
  score: number
  time_used_ms: number | null
  memory_used_kb: number | null
  error_message?: string | null
  created_at?: string
  cases?: SubmissionCaseResult[]
}

export interface SubmissionCaseResult {
  id: string
  case_name: string | null
  status: string
  time_used_ms: number | null
  memory_used_kb: number | null
  score: number
  output: string | null
}

// ---------------- 管理模块（docs/contracts/admin.md） ----------------

export type ConfigCategory =
  | 'site'
  | 'auth_email'
  | 'team'
  | 'contest'
  | 'model'
  | 'token'
  | 'sandbox'
  | 'log'
  | 'community'

export interface SystemConfigItem {
  id: string
  category: ConfigCategory
  config_key: string
  config_value: unknown
  description: string | null
  updated_by: string | null
  updated_at: string
}

export type LogType = 'request' | 'login' | 'exception'

export interface RequestLogRow {
  id: string
  request_id: string
  user_id: string | null
  method: string
  path: string
  status_code: number
  ip_address: string | null
  duration_ms: number | null
  created_at: string
}

export interface LoginLogRow {
  id: string
  user_id: string | null
  email: string | null
  action: string
  ip_address: string | null
  success: boolean
  reason: string | null
  created_at: string
}

export interface ExceptionLogRow {
  id: string
  level: 'error' | 'warning' | 'fatal'
  message: string
  traceback: string | null
  request_id: string | null
  user_id: string | null
  created_at: string
}

export type SandboxNodeStatus = 'online' | 'offline'

export interface SandboxNode {
  id: string
  name: string
  status: SandboxNodeStatus
  /** 0~1 负载 */
  load: number
  cpu_usage: number
  memory_usage: number
  running_tasks: number
  last_heartbeat_at: string
  version: string
}

export type ReportStatus = 'pending' | 'handled' | 'ignored'
export type ReportType = 'problem' | 'solution' | 'post' | 'comment' | 'user'

export interface Report {
  id: string
  target_type: ReportType
  target_id: string
  /** 目标内容摘要（内容表实现后回填；当前可能为 null） */
  target_summary: string | null
  reporter_nickname: string
  reason: string
  status: ReportStatus
  handled_by: string | null
  handled_at: string | null
  created_at: string
}
