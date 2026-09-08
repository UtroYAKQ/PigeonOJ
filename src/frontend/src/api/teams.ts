/**
 * 团队模块 API（docs/contracts/teams.md）。
 * 团队角色经后端 user_roles（scope='team'）判定；前端按 TeamDetail.my_role 控制交互显隐。
 */
import { apiRequest } from './http'
import { buildQuery } from '@/utils/query'
import type {
  ContestCreatePayload,
  ContestSummary,
  PageResult,
  ProblemDetail,
  ProblemSetDetail,
  ProblemSetItemsPayload,
  ProblemSetSummary,
  TeamApplicationItem,
  TeamDetail,
  TeamInviteCreated,
  TeamInviteResolved,
  TeamListQuery,
  TeamMemberItem,
  TeamProblemListQuery,
  TeamProblemReferencePayload,
  TeamProblemSummary,
  TeamSetCreatePayload,
  TeamSetListQuery,
  TeamSummary,
  TeamContestListQuery,
  TeamUpsertPayload,
} from '@/types'

/** 创建团队（admin/tutor） */
export function createTeam(body: TeamUpsertPayload): Promise<TeamSummary> {
  return apiRequest('POST', '/teams', body)
}

/** 团队中心列表：默认仅公开在册团队；mine=true 为「我的团队」勾选（须登录） */
export function listTeams(
  query: TeamListQuery = {},
): Promise<PageResult<TeamSummary>> {
  return apiRequest('GET', `/teams${buildQuery(query)}`)
}

/** 我的团队列表（在册成员；带成员数与我的角色；keyword 模糊匹配团队名称） */
export function listMyTeams(
  query: { page?: number; page_size?: number; keyword?: string } = {},
): Promise<{ items: TeamSummary[]; total: number; page: number; page_size: number }> {
  return apiRequest('GET', `/teams/mine${buildQuery(query)}`)
}

/** 团队详情（成员可见） */
export function getTeam(id: string): Promise<TeamDetail> {
  return apiRequest('GET', `/teams/${id}`)
}

/** 编辑团队信息（team_creator / team_admin；缺省不动） */
export function updateTeam(id: string, body: Partial<TeamUpsertPayload>): Promise<TeamDetail> {
  return apiRequest('PUT', `/teams/${id}`, body)
}

/** 成员列表（团队任意角色可查；keyword 模糊昵称） */
export function listTeamMembers(
  id: string,
  query: { page?: number; page_size?: number; keyword?: string; status?: string } = {},
): Promise<{ items: TeamMemberItem[]; total: number; page: number; page_size: number }> {
  return apiRequest('GET', `/teams/${id}/members${buildQuery(query)}`)
}

/** 生成邀请链接（team_creator / team_admin；写 Redis，TTL 取配置） */
export function createTeamInvite(id: string): Promise<TeamInviteCreated> {
  return apiRequest('POST', `/teams/${id}/invites`)
}

/** 解析邀请链接（public） */
export function resolveTeamInvite(token: string): Promise<TeamInviteResolved> {
  return apiRequest('GET', `/teams/invites/${token}`)
}

/** 提交加入申请（invite_token 可选） */
export function submitTeamApplication(id: string, inviteToken?: string): Promise<null> {
  return apiRequest('POST', `/teams/${id}/applications`, {
    invite_token: inviteToken || undefined,
  })
}

/** 申请列表（team_creator / team_admin；status 缺省 = pending） */
export function listTeamApplications(
  id: string,
  query: { page?: number; page_size?: number; status?: string } = {},
): Promise<{ items: TeamApplicationItem[]; total: number; page: number; page_size: number }> {
  return apiRequest('GET', `/teams/${id}/applications${buildQuery(query)}`)
}

/** 审批加入申请（通过写在册成员 + team_member 授权） */
export function reviewTeamApplication(
  id: string,
  applicationId: string,
  approve: boolean,
): Promise<null> {
  return apiRequest('POST', `/teams/${id}/applications/${applicationId}/review`, { approve })
}

/** 分配 / 取消团队管理员（仅创建者） */
export function setTeamAdmin(id: string, userId: string, isAdmin: boolean): Promise<null> {
  return apiRequest('POST', `/teams/${id}/members/${userId}/admin`, { is_admin: isAdmin })
}

/** 踢出成员（team_creator / team_admin） */
export function kickTeamMember(id: string, userId: string): Promise<null> {
  return apiRequest('DELETE', `/teams/${id}/members/${userId}`)
}

/** 主动退出（成员本人；创建者不可退出） */
export function exitTeam(id: string): Promise<null> {
  return apiRequest('POST', `/teams/${id}/exit`)
}

/** 解散团队（软解散，仅创建者） */
export function disbandTeam(id: string): Promise<null> {
  return apiRequest('DELETE', `/teams/${id}`)
}

/* ==================== 团队空间（题库 / 题单 / 比赛，docs/contracts/teams.md 团队空间节） ==================== */

/** 团队题库列表：成员见 team_visible；创建者 / 管理员另见 admin_visible 与本人草稿 */
export function listTeamProblems(
  teamId: string,
  query: TeamProblemListQuery = {},
): Promise<PageResult<TeamProblemSummary>> {
  return apiRequest('GET', `/teams/${teamId}/problems${buildQuery(query)}`)
}

/** 引用本人全站题目进入团队题库（team_creator / team_admin；单向，无移出通道） */
export function referenceTeamProblem(
  teamId: string,
  body: TeamProblemReferencePayload,
): Promise<TeamProblemSummary> {
  return apiRequest('POST', `/teams/${teamId}/problems/references`, body)
}

/** 团队编排候选搜索（team_creator / team_admin）：本团队题目 ∪ 全站公开 ∪ 本人私有 */
export function searchTeamArrangeableProblems(
  teamId: string,
  query: { keyword?: string; page?: number; page_size?: number } = {},
): Promise<PageResult<TeamProblemSummary>> {
  return apiRequest('GET', `/teams/${teamId}/problems/arrangeable${buildQuery(query)}`)
}

/** 团队题目引用候选搜索（team_creator / team_admin）：本人创建 + 已发布 +
 * 全站题 + 未被该团队引用过（同团队同源仅一份快照） */
export function searchTeamReferenceableProblems(
  teamId: string,
  query: { keyword?: string; page?: number; page_size?: number } = {},
): Promise<PageResult<TeamProblemSummary>> {
  return apiRequest('GET', `/teams/${teamId}/problems/referenceable${buildQuery(query)}`)
}

/** 团队题库内题目详情（统一入口）：团队可见 + 归属校验后与题库详情装配一致 */
export function getTeamProblem(teamId: string, problemId: string): Promise<ProblemDetail> {
  return apiRequest('GET', `/teams/${teamId}/problems/${problemId}`)
}

/** 团队上下文编辑题面（编辑向导第一步）：成员门 + 归属校验后复用题库 update */
export function updateTeamProblemStatement(
  teamId: string,
  problemId: string,
  body: import('@/types').ProblemEditPayload,
): Promise<TeamProblemSummary> {
  return apiRequest('PUT', `/teams/${teamId}/problems/${problemId}/statement`, body)
}

/** 团队题库内交题（统一入口）：团队门控通过后走统一判题链路 */
export function createTeamProblemSubmission(
  teamId: string,
  problemId: string,
  body: { language: string; code: string },
): Promise<{ submission_id: string; status: string }> {
  return apiRequest('POST', `/teams/${teamId}/problems/${problemId}/submissions`, body)
}

/** 团队题库内用户自测（豁免题库可见性；经团队上下文端点派发） */
export function runTeamProblemCode(
  teamId: string,
  problemId: string,
  body: { language: string; code: string; input?: string },
): Promise<import('@/types').SelfTestResult> {
  return apiRequest('POST', `/teams/${teamId}/problems/${problemId}/run-code`, body)
}

/** 团队题单列表（默认仅未下线；团队管理视图可传 status） */
export function listTeamProblemSets(
  teamId: string,
  query: TeamSetListQuery = {},
): Promise<PageResult<ProblemSetSummary>> {
  return apiRequest('GET', `/teams/${teamId}/problem-sets${buildQuery(query)}`)
}

/** 团队题单详情（团队上下文统一入口；不走 /problem-sets/{id}） */
export function getTeamProblemSet(teamId: string, setId: string): Promise<ProblemSetDetail> {
  return apiRequest('GET', `/teams/${teamId}/problem-sets/${setId}`)
}

/** 团队题单内题目详情（团队上下文统一入口） */
export function getTeamSetProblem(
  teamId: string,
  setId: string,
  problemId: string,
): Promise<ProblemDetail> {
  return apiRequest('GET', `/teams/${teamId}/problem-sets/${setId}/problems/${problemId}`)
}

/** 团队题单内交题（团队上下文统一入口） */
export function createTeamSetProblemSubmission(
  teamId: string,
  setId: string,
  problemId: string,
  body: { language: string; code: string },
): Promise<{ submission_id: string; status: string }> {
  return apiRequest(
    'POST',
    `/teams/${teamId}/problem-sets/${setId}/problems/${problemId}/submissions`,
    body,
  )
}

/** 团队题单内用户自测（豁免题库可见性；团队上下文派发） */
export function runTeamSetProblemCode(
  teamId: string,
  setId: string,
  problemId: string,
  body: { language: string; code: string; input?: string },
): Promise<import('@/types').SelfTestResult> {
  return apiRequest(
    'POST',
    `/teams/${teamId}/problem-sets/${setId}/problems/${problemId}/run-code`,
    body,
  )
}

/** 创建团队题单（team_creator / team_admin；visibility='team'；copy_from_set_id 非空 = 复制本人全站题单条目） */
export function createTeamProblemSet(
  teamId: string,
  body: TeamSetCreatePayload,
): Promise<ProblemSetSummary> {
  return apiRequest('POST', `/teams/${teamId}/problem-sets`, body)
}

/** 编排团队题单（team_creator / team_admin）：候选 = 本团队题目 ∪ 全站公开 ∪ 本人私有 */
export function replaceTeamProblemSetItems(
  teamId: string,
  setId: string,
  body: ProblemSetItemsPayload,
): Promise<null> {
  return apiRequest('PUT', `/teams/${teamId}/problem-sets/${setId}/items`, body)
}

/** 下线团队题单（team_creator / team_admin；不做物理删除） */
export function archiveTeamProblemSet(teamId: string, setId: string): Promise<ProblemSetSummary> {
  return apiRequest('POST', `/teams/${teamId}/problem-sets/${setId}/archive`)
}

/** 团队比赛列表（成员可见，全部状态） */
export function listTeamContests(
  teamId: string,
  query: TeamContestListQuery = {},
): Promise<PageResult<ContestSummary>> {
  return apiRequest('GET', `/teams/${teamId}/contests${buildQuery(query)}`)
}

/** 创建团队比赛（team_creator / team_admin；contest_type='team'） */
export function createTeamContest(
  teamId: string,
  body: ContestCreatePayload,
): Promise<ContestSummary> {
  return apiRequest('POST', `/teams/${teamId}/contests`, body)
}
