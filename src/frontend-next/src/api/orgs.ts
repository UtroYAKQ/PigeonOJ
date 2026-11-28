/**
 * 组织模块 API（docs/contracts.md §5）。
 * 组织角色由后端 user_roles（scope='org'）判定；前端按 OrgDetail.my_role 控制交互显隐。
 * 组织题库管理动作复用题库统一端点；仅「创建」必须走组织端点。
 */
import { apiRequest } from './http'
import { buildQuery } from '@/utils/query'
import type {
  OrgCreatePayload,
  OrgDetail,
  OrgListQuery,
  OrgMemberCandidate,
  OrgMemberItem,
  OrgMemberListQuery,
  OrgProblemListQuery,
  OrgSummary,
  OrgTeamListQuery,
  OrgUpdatePayload,
  PageResult,
  ProblemCreatePayload,
  ProblemDetail,
  TeamProblemSummary,
  TeamSummary,
  TeamUpsertPayload,
} from '@/types'

/** 创建组织（admin；创建者不加入组织，仅任命 admin_user_ids 为初始组织管理员） */
export function createOrg(body: OrgCreatePayload): Promise<OrgDetail> {
  return apiRequest('POST', '/orgs', body)
}

/** 我加入的组织列表（active；带 my_role / 成员数 / 团队数） */
export function listMyOrgs(query: OrgListQuery = {}): Promise<PageResult<OrgSummary>> {
  return apiRequest('GET', `/orgs/mine${buildQuery(query)}`)
}

export function getOrg(id: string): Promise<OrgDetail> {
  return apiRequest('GET', `/orgs/${id}`)
}

export function updateOrg(id: string, body: OrgUpdatePayload): Promise<OrgDetail> {
  return apiRequest('PUT', `/orgs/${id}`, body)
}

/** 解散组织（admin；软解散，题库归档、团队级联解散） */
export function disbandOrg(id: string): Promise<null> {
  return apiRequest('DELETE', `/orgs/${id}`)
}

export function listOrgMembers(
  id: string,
  query: OrgMemberListQuery = {},
): Promise<PageResult<OrgMemberItem>> {
  return apiRequest('GET', `/orgs/${id}/members${buildQuery(query)}`)
}

export function addOrgMembers(id: string, userIds: string[]): Promise<null> {
  return apiRequest('POST', `/orgs/${id}/members`, { user_ids: userIds })
}

/** 按邮箱精确查找可添加的组织成员（org_admin / 站点 admin；仅 active） */
export function lookupOrgMemberCandidates(
  id: string,
  email: string,
): Promise<OrgMemberCandidate[]> {
  return apiRequest('GET', `/orgs/${id}/member-candidates${buildQuery({ email })}`)
}

export function removeOrgMember(id: string, userId: string): Promise<null> {
  return apiRequest('DELETE', `/orgs/${id}/members/${userId}`)
}

export function setOrgMemberAdmin(
  id: string,
  userId: string,
  isAdmin: boolean,
): Promise<null> {
  return apiRequest('PUT', `/orgs/${id}/members/${userId}/admin`, { is_admin: isAdmin })
}

export function setOrgMemberNote(
  id: string,
  userId: string,
  note: string | null,
): Promise<null> {
  return apiRequest('PUT', `/orgs/${id}/members/${userId}/note`, { note })
}

/** 在组织内创建团队（org_admin；teams.org_id 落本组织） */
export function createOrgTeam(
  orgId: string,
  body: TeamUpsertPayload,
): Promise<TeamSummary> {
  return apiRequest('POST', `/orgs/${orgId}/teams`, body)
}

export function listOrgTeams(
  orgId: string,
  query: OrgTeamListQuery = {},
): Promise<PageResult<TeamSummary>> {
  return apiRequest('GET', `/orgs/${orgId}/teams${buildQuery(query)}`)
}

/** 组织题库列表：缺省 published；status='draft' 为全组织草稿视图 */
export function listOrgProblems(
  orgId: string,
  query: OrgProblemListQuery = {},
): Promise<PageResult<TeamProblemSummary>> {
  return apiRequest('GET', `/orgs/${orgId}/problems${buildQuery(query)}`)
}

/** 组织题库直建题目（visibility 恒 org_visible，服务端强制） */
export function createOrgProblem(
  orgId: string,
  body: ProblemCreatePayload,
): Promise<TeamProblemSummary> {
  return apiRequest('POST', `/orgs/${orgId}/problems`, body)
}

/** 组织题目详情（组织上下文统一入口） */
export function getOrgProblem(orgId: string, problemId: string): Promise<ProblemDetail> {
  return apiRequest('GET', `/orgs/${orgId}/problems/${problemId}`)
}