/**
 * 管理 / 运维模块 API（docs/contracts/admin.md）：用户管理 / 系统配置 / 日志 / 沙箱状态 / 举报。
 * 所有端点权限为 admin（后端 2003 拦截非管理员）。
 * 注：模型配置与 Token 用量端点随 AI 模块暂缓实现，未包含在本模块。
 */
import { apiRequest } from './http'
import { buildQuery } from '@/utils/query'
import type {
  AdminProblemSetListQuery,
  AdminSubmission,
  AdminTeamListQuery,
  AdminUserQuery,
  ConfigCategory,
  ContestListQuery,
  ContestSummary,
  GlobalRoleCode,
  LogQuery,
  LogType,
  OnlineUser,
  PageResult,
  ProblemSetSummary,
  ProblemTagItem,
  Report,
  ReportStatus,
  SandboxNode,
  SystemConfigItem,
  TeamAdminDetail,
  TeamAdminSummary,
  TeamMemberItem,
  TeamProblemSummary,
  User,
} from '@/types'

// ---------------- 管理列表（单一所有权模型：admin 全量、tutor 等仅本人创建） ----------------

/** GET /admin/users/online — 在线用户面板（10 分钟窗口内有活跃回写的有效会话） */
export function adminListOnlineUsers(query: { page?: number; page_size?: number } = {}) {
  return apiRequest<PageResult<OnlineUser>>('GET', `/admin/users/online${buildQuery(query)}`)
}

export interface AdminSubmissionQuery {
  page?: number
  page_size?: number
  submit_type?: string
  status?: string
  language?: string
  keyword?: string
  problem_id?: string
}

/** GET /admin/submissions — 全站提交面板（提交类型 / 用户 / 题目 / 状态 / 语言筛选） */
export function adminListSubmissions(query: AdminSubmissionQuery = {}) {
  return apiRequest<PageResult<AdminSubmission>>('GET', `/admin/submissions${buildQuery(query)}`)
}

/** GET /admin/contests — 比赛管理视图（admin 全量、tutor 仅本人创建，全部状态） */
export function adminListContests(query: ContestListQuery = {}) {
  return apiRequest<PageResult<ContestSummary>>('GET', `/admin/contests${buildQuery(query)}`)
}

/** GET /admin/problem-sets — 题单管理视图（admin 全量、tutor 仅本人创建，含私有与已下线；ownership 过滤来源） */
export function adminListProblemSets(query: AdminProblemSetListQuery = {}) {
  return apiRequest<PageResult<ProblemSetSummary>>('GET', `/admin/problem-sets${buildQuery(query)}`)
}

// ---------------- 团队管理（docs/contracts/teams.md 管理端：admin 全量只读浏览） ----------------

/** GET /admin/teams — 团队管理列表（admin 全量，含已解散；成员数 / 创建人昵称 / 状态） */
export function adminListTeams(query: AdminTeamListQuery = {}) {
  return apiRequest<PageResult<TeamAdminSummary>>('GET', `/admin/teams${buildQuery(query)}`)
}

/** GET /admin/teams/:id — 团队管理详情（免团队成员校验，含已解散团队） */
export function adminGetTeam(teamId: string) {
  return apiRequest<TeamAdminDetail>('GET', `/admin/teams/${teamId}`)
}

/** GET /admin/teams/:id/members — 团队成员列表（admin 管理视图；keyword 模糊昵称） */
export function adminListTeamMembers(
  teamId: string,
  query: { page?: number; page_size?: number; keyword?: string; status?: string } = {},
) {
  return apiRequest<PageResult<TeamMemberItem>>(
    'GET',
    `/admin/teams/${teamId}/members${buildQuery(query)}`,
  )
}

/** GET /admin/teams/:id/problems — 团队题库列表（admin 管理视图：全部状态 / 可见性） */
export function adminListTeamProblems(
  teamId: string,
  query: {
    page?: number
    page_size?: number
    keyword?: string
    status?: 'draft' | 'published' | 'archived'
    visibility?: 'admin_visible' | 'team_visible'
  } = {},
) {
  return apiRequest<PageResult<TeamProblemSummary>>(
    'GET',
    `/admin/teams/${teamId}/problems${buildQuery(query)}`,
  )
}

/** GET /admin/teams/:id/problem-sets — 团队题单列表（admin 管理视图：含已下线） */
export function adminListTeamProblemSets(
  teamId: string,
  query: {
    page?: number
    page_size?: number
    keyword?: string
    status?: 'active' | 'archived'
  } = {},
) {
  return apiRequest<PageResult<ProblemSetSummary>>(
    'GET',
    `/admin/teams/${teamId}/problem-sets${buildQuery(query)}`,
  )
}

/** GET /admin/teams/:id/contests — 团队比赛列表（admin 管理视图：全部状态） */
export function adminListTeamContests(
  teamId: string,
  query: {
    page?: number
    page_size?: number
    keyword?: string
    status?: 'scheduled' | 'running' | 'finished'
  } = {},
) {
  return apiRequest<PageResult<ContestSummary>>(
    'GET',
    `/admin/teams/${teamId}/contests${buildQuery(query)}`,
  )
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

/** POST /admin/users/:id/freeze — 冻结（短时封禁：duration_minutes 到期自动恢复，缺省 15 分钟） */
export function adminFreezeUser(userId: string, reason: string, durationMinutes?: number) {
  return apiRequest<null>('POST', `/admin/users/${userId}/freeze`, {
    reason,
    duration_minutes: durationMinutes,
  })
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
