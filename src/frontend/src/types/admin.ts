/**
 * 管理 / 运维模块类型（docs/contracts/admin.md）。
 */

// ---------------- 系统配置 ----------------

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

// ---------------- 日志 ----------------

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

export interface LogQuery {
  page?: number
  page_size?: number
  keyword?: string
  start?: string
  end?: string
}

// ---------------- 沙箱状态 ----------------

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

// ---------------- 用户管理查询 ----------------

export interface AdminUserQuery {
  page?: number
  page_size?: number
  keyword?: string
  status?: string
}

// ---------------- 举报 ----------------

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
