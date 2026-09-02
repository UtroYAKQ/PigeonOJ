/**
 * 团队模块 API（docs/contracts/teams.md）。
 * 团队角色经后端 user_roles（scope='team'）判定；前端按 TeamDetail.my_role 控制交互显隐。
 */
import { apiRequest } from './http'
import { buildQuery } from '@/utils/query'
import type {
  TeamApplicationItem,
  TeamDetail,
  TeamInviteCreated,
  TeamInviteResolved,
  TeamMemberItem,
  TeamSummary,
  TeamUpsertPayload,
} from '@/types'

/** 创建团队（admin/tutor） */
export function createTeam(body: TeamUpsertPayload): Promise<TeamSummary> {
  return apiRequest('POST', '/teams', body)
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

/** 成员列表（团队任意角色可查） */
export function listTeamMembers(
  id: string,
  query: { page?: number; page_size?: number; status?: string } = {},
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
