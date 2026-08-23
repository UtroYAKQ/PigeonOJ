/**
 * 管理 / 运维模块 API（docs/contracts/admin.md）：用户管理 / 系统配置 / 日志 / 沙箱状态 / 举报。
 * 所有端点权限为 admin（后端 2003 拦截非管理员）。
 * 注：模型配置与 Token 用量端点随 AI 模块暂缓实现，未包含在本模块。
 */
import { apiRequest } from './request'
import type {
  AdminUserQuery,
  ConfigCategory,
  GlobalRoleCode,
  LogQuery,
  LogType,
  PageResult,
  Report,
  ReportStatus,
  SandboxNode,
  SystemConfigItem,
  User,
} from '@/types'

// ---------------- 用户管理 ----------------

/** GET /admin/users — 用户列表 */
export function adminListUsers(query: AdminUserQuery = {}) {
  const params = new URLSearchParams()
  if (query.page) params.set('page', String(query.page))
  if (query.page_size) params.set('page_size', String(query.page_size))
  if (query.keyword) params.set('keyword', query.keyword)
  if (query.status) params.set('status', query.status)
  const qs = params.toString()
  return apiRequest<PageResult<User>>('GET', `/admin/users${qs ? `?${qs}` : ''}`)
}

/** PUT /admin/users/:id/roles — 全局角色授权（scope='global'） */
export function adminSetRoles(userId: string, roleIds: GlobalRoleCode[]) {
  return apiRequest<null>('PUT', `/admin/users/${userId}/roles`, { role_ids: roleIds })
}

/** POST /admin/users/:id/ban — 封禁 */
export function adminBanUser(userId: string, reason: string) {
  return apiRequest<null>('POST', `/admin/users/${userId}/ban`, { reason })
}

/** POST /admin/users/:id/unban — 解封 */
export function adminUnbanUser(userId: string) {
  return apiRequest<null>('POST', `/admin/users/${userId}/unban`)
}

/** POST /admin/users/:id/freeze — 冻结 */
export function adminFreezeUser(userId: string, reason: string) {
  return apiRequest<null>('POST', `/admin/users/${userId}/freeze`, { reason })
}

/** POST /admin/users/:id/unfreeze — 解冻 */
export function adminUnfreezeUser(userId: string) {
  return apiRequest<null>('POST', `/admin/users/${userId}/unfreeze`)
}

// ---------------- 系统配置 ----------------

/** GET /admin/configs — 按域读取系统配置 */
export function adminListConfigs(category?: ConfigCategory | '') {
  const qs = category ? `?category=${encodeURIComponent(category)}` : ''
  return apiRequest<SystemConfigItem[]>('GET', `/admin/configs${qs}`)
}

/** PUT /admin/configs — 批量保存配置（修改人记录 updated_by） */
export function adminUpdateConfigs(items: Array<{ id: string; config_value: unknown }>) {
  return apiRequest<SystemConfigItem[]>('PUT', '/admin/configs', { items })
}

// ---------------- 日志 ----------------

/** GET /admin/logs/:type — 日志查询（request / login / exception） */
export function adminListLogs(type: LogType, query: LogQuery = {}) {
  const params = new URLSearchParams()
  if (query.page) params.set('page', String(query.page))
  if (query.page_size) params.set('page_size', String(query.page_size))
  if (query.keyword) params.set('keyword', query.keyword)
  if (query.start) params.set('start', query.start)
  if (query.end) params.set('end', query.end)
  const qs = params.toString()
  return apiRequest<PageResult<unknown>>('GET', `/admin/logs/${type}${qs ? `?${qs}` : ''}`)
}

// ---------------- 沙箱状态 ----------------

/** GET /admin/sandbox/status — 沙箱节点状态（读 Redis 热数据） */
export function adminSandboxStatus() {
  return apiRequest<SandboxNode[]>('GET', '/admin/sandbox/status')
}

// ---------------- 举报 ----------------

/** GET /admin/reports — 举报列表 */
export function adminListReports(query: { page?: number; page_size?: number; status?: ReportStatus | '' } = {}) {
  const params = new URLSearchParams()
  if (query.page) params.set('page', String(query.page))
  if (query.page_size) params.set('page_size', String(query.page_size))
  if (query.status) params.set('status', query.status)
  const qs = params.toString()
  return apiRequest<PageResult<Report>>('GET', `/admin/reports${qs ? `?${qs}` : ''}`)
}

/** POST /admin/reports/:id/handle — 处理举报（handled 通过 / ignored 驳回，docs/contracts/community.md） */
export function adminHandleReport(reportId: string, action: 'handled' | 'ignored') {
  return apiRequest<null>('POST', `/admin/reports/${reportId}/handle`, { action })
}
