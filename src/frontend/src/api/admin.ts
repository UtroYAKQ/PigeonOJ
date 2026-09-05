/**
 * 管理 / 运维模块 API（docs/contracts/admin.md）：用户管理 / 系统配置 / 日志 / 沙箱状态 / 举报。
 * 所有端点权限为 admin（后端 2003 拦截非管理员）。
 * 注：模型配置与 Token 用量端点随 AI 模块暂缓实现，未包含在本模块。
 */
import { apiRequest } from './http'
import { buildQuery } from '@/utils/query'
import type {
  AdminUserQuery,
  ConfigCategory,
  ContestListQuery,
  ContestSummary,
  GlobalRoleCode,
  LogQuery,
  LogType,
  PageResult,
  ProblemSetListQuery,
  ProblemSetSummary,
  ProblemTagItem,
  Report,
  ReportStatus,
  SandboxNode,
  SystemConfigItem,
  User,
} from '@/types'

// ---------------- 管理列表（单一所有权模型：admin 全量、tutor 等仅本人创建） ----------------

/** GET /admin/contests — 比赛管理视图（admin 全量、tutor 仅本人创建，全部状态） */
export function adminListContests(query: ContestListQuery = {}) {
  return apiRequest<PageResult<ContestSummary>>('GET', `/admin/contests${buildQuery(query)}`)
}

/** GET /admin/problem-sets — 题单管理视图（admin 全量、tutor 仅本人创建，含私有与已下线） */
export function adminListProblemSets(
  query: ProblemSetListQuery & { status?: 'active' | 'archived' } = {},
) {
  return apiRequest<PageResult<ProblemSetSummary>>('GET', `/admin/problem-sets${buildQuery(query)}`)
}

// ---------------- 用户管理 ----------------

/** GET /admin/users — 用户列表 */
export function adminListUsers(query: AdminUserQuery = {}) {
  return apiRequest<PageResult<User>>('GET', `/admin/users${buildQuery(query)}`)
}

/** PUT /admin/users/:id/roles — 全局角色授权（单一角色模型，scope='global'） */
export function adminSetRole(userId: string, roleId: GlobalRoleCode) {
  return apiRequest<null>('PUT', `/admin/users/${userId}/roles`, { role_id: roleId })
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
  return apiRequest<PageResult<unknown>>('GET', `/admin/logs/${type}${buildQuery(query)}`)
}

/** DELETE /admin/logs/:type — 一键清空指定类型日志（admin 危险操作） */
export function adminClearLogs(type: LogType) {
  return apiRequest<null>('DELETE', `/admin/logs/${type}`)
}

// ---------------- 沙箱状态 ----------------

/** GET /admin/sandbox/status — 沙箱节点状态（读 Redis 热数据） */
export function adminSandboxStatus() {
  return apiRequest<SandboxNode[]>('GET', '/admin/sandbox/status')
}

// ---------------- 举报 ----------------

/** GET /admin/reports — 举报列表 */
export function adminListReports(
  query: { page?: number; page_size?: number; status?: ReportStatus | null } = {},
) {
  return apiRequest<PageResult<Report>>('GET', `/admin/reports${buildQuery(query)}`)
}

/** POST /admin/reports/:id/handle — 处理举报（handled 通过 / ignored 驳回，docs/contracts/community.md） */
export function adminHandleReport(reportId: string, action: 'handled' | 'ignored') {
  return apiRequest<null>('POST', `/admin/reports/${reportId}/handle`, { action })
}

// ---------------- 标签管理（docs/contracts/problems.md /admin/tags*） ----------------

/** GET /admin/tags — 标签管理分页列表（含已归档，激活在前；keyword 模糊匹配标签名） */
export function adminListTags(query: { page: number; page_size: number; keyword?: string }) {
  return apiRequest<PageResult<ProblemTagItem>>('GET', `/admin/tags${buildQuery(query)}`)
}

/** POST /admin/tags — 新增标签（name 全局唯一） */
export function adminCreateTag(body: { name: string; color?: string | null }) {
  return apiRequest<ProblemTagItem>('POST', '/admin/tags', body)
}

/** PUT /admin/tags/:id — 修改名称 / 颜色 */
export function adminUpdateTag(tagId: string, body: { name?: string; color?: string | null }) {
  return apiRequest<ProblemTagItem>('PUT', `/admin/tags/${tagId}`, body)
}

/** POST /admin/tags/:id/archive — 归档（关联保留、不再可选） */
export function adminArchiveTag(tagId: string) {
  return apiRequest<ProblemTagItem>('POST', `/admin/tags/${tagId}/archive`)
}
