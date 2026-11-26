/**
 * 组织模块 API（docs/contracts/orgs.md）。
 * 组织角色经后端 user_roles（scope='org'）判定；前端按 OrgDetail.my_role 控制交互显隐。
 * 组织题库管理动作复用题库统一端点（/problems/{id}/...，权限门按组织扩展），
 * 仅「创建」必须走组织端点（POST /orgs/{id}/problems）。
 */
import { apiRequest } from './http'
import { buildQuery } from '@/utils/query'
import type {
  OrgCreatePayload,
  OrgDetail,
  OrgListQuery,
  OrgMemberItem,
  OrgMemberListQuery,
  OrgProblemListQuery,
  OrgSummary,
  OrgTeamListQuery,
  OrgUpdatePayload,
  PageResult,
  ProblemCreatePayload,
  ProblemDetail,
  TeamSummary,
  TeamUpsertPayload,
  TeamProblemSummary,
} from '@/types'

/** 创建组织（admin；name 全站唯一，可同时任命初始组织管理员） */
export function createOrg(body: OrgCreatePayload): Promise<OrgDetail> {
  return apiRequest('POST', '/orgs', body)
}

/** 我的组织列表（在册组织；带 my_role / 成员数 / 团队数；keyword 模糊名称） */
export function listMyOrgs(
  query: OrgListQuery = {},
): Promise<PageResult<OrgSummary>> {
  return apiRequest('GET', `/orgs/mine${buildQuery(query)}`)
}

/** 组织详情（成员可见；非成员 2003） */
export function getOrg(id: string): Promise<OrgDetail> {
  return apiRequest('GET', `/orgs/${id}`)
}

/** 编辑组织信息（org_admin；缺省不动） */
export function updateOrg(id: string, body: OrgUpdatePayload): Promise<OrgDetail> {
  return apiRequest('PUT', `/orgs/${id}`, body)
}

/** 解散组织（admin；软解散，题库题目归档、授权全清） */
export function disbandOrg(id: string): Promise<null> {
  return apiRequest('DELETE', `/orgs/${id}`)
}

/** 组织成员列表（org 角色可查；keyword 模糊昵称） */
export function listOrgMembers(
  id: string,
  query: OrgMemberListQuery = {},
): Promise<PageResult<OrgMemberItem>> {
  return apiRequest('GET', `/orgs/${id}/members${buildQuery(query)}`)
}

/** 直接添加成员（org_admin；可批量，已在册跳过） */
export function addOrgMembers(id: string, userIds: string[]): Promise<null> {
  return apiRequest('POST', `/orgs/${id}/members`, { user_ids: userIds })
}

/** 移出成员（org_admin；同步清授权，最后一名 org_admin 3004） */
export function removeOrgMember(id: string, userId: string): Promise<null> {
  return apiRequest('DELETE', `/orgs/${id}/members/${userId}`)
}

/** 授予 / 撤销组织管理员（org_admin / admin；最后一名 3004） */
export function setOrgMemberAdmin(id: string, userId: string, isAdmin: boolean): Promise<null> {
  return apiRequest('PUT', `/orgs/${id}/members/${userId}/admin`, { is_admin: isAdmin })
}

/** 设置成员备注（本人 或 org_admin；空串 = 清除） */
export function setOrgMemberNote(id: string, userId: string, note: string | null): Promise<null> {
  return apiRequest('PUT', `/orgs/${id}/members/${userId}/note`, { note })
}

/** 创建团队（org_admin；teams.org_id 固定为本组织，创建者自动 team_creator） */
export function createOrgTeam(orgId: string, body: TeamUpsertPayload): Promise<TeamSummary> {
  return apiRequest('POST', `/orgs/${orgId}/teams`, body)
}

/** 组织名下团队列表（org 角色可查；带成员数 / 状态 / my_role） */
export function listOrgTeams(
  orgId: string,
  query: OrgTeamListQuery = {},
): Promise<PageResult<TeamSummary>> {
  return apiRequest('GET', `/orgs/${orgId}/teams${buildQuery(query)}`)
}

/** 组织题库列表：缺省 published；status='draft' 草稿箱视图（全组织草稿）；归档不返回 */
export function listOrgProblems(
  orgId: string,
  query: OrgProblemListQuery = {},
): Promise<PageResult<TeamProblemSummary>> {
  return apiRequest('GET', `/orgs/${orgId}/problems${buildQuery(query)}`)
}

/** 组织题库直建题目（org_member；visibility 恒 org_visible 由服务端强制） */
export function createOrgProblem(
  orgId: string,
  body: ProblemCreatePayload,
): Promise<TeamProblemSummary> {
  return apiRequest('POST', `/orgs/${orgId}/problems`, body)
}

/** 组织题目详情（组织上下文统一入口，复用题库详情装配） */
export function getOrgProblem(orgId: string, problemId: string): Promise<ProblemDetail> {
  return apiRequest('GET', `/orgs/${orgId}/problems/${problemId}`)
}
