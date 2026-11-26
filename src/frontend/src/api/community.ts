/**
 * 社区模块 API（docs/contracts/community.md）：官方题解 / 用户题解 / 代码广场 / 评论 / 举报。
 */
import { apiRequest } from './http'
import { buildQuery } from '@/utils/query'
import type {
  AdminCodeShare,
  AdminSolution,
  CodeShareDetail,
  CodeShareLanguage,
  CodeSharePayload,
  CodeShareStatus,
  CodeShareSummary,
  CommentAdminContext,
  CommentNode,
  CommentPayload,
  CommentTargetType,
  EditorialView,
  PageResult,
  ReportPayload,
  SolutionDetail,
  SolutionPayload,
  SolutionStatus,
  SolutionSummary,
} from '@/types'

/** 官方题解（比赛进行中后端 3002，由调用方按信封错误提示） */
export function getEditorial(problemId: string): Promise<EditorialView> {
  return apiRequest('GET', `/problems/${problemId}/editorial`)
}

/** 题解分享分页（published；mine=true 返回本人全部状态，需登录） */
export function listSolutions(
  problemId: string,
  query: { page?: number; page_size?: number; keyword?: string; mine?: boolean } = {},
): Promise<PageResult<SolutionSummary>> {
  return apiRequest('GET', `/problems/${problemId}/solutions${buildQuery(query)}`)
}

export function createSolution(
  problemId: string,
  payload: SolutionPayload,
): Promise<SolutionDetail> {
  return apiRequest('POST', `/problems/${problemId}/solutions`, payload)
}

export function getSolution(id: string): Promise<SolutionDetail> {
  return apiRequest('GET', `/solutions/${id}`)
}

export function updateSolution(
  id: string,
  payload: Partial<SolutionPayload>,
): Promise<SolutionDetail> {
  return apiRequest('PUT', `/solutions/${id}`, payload)
}

/** 下架自己的题解（软删；owner / admin） */
export function deleteSolution(id: string): Promise<void> {
  return apiRequest('DELETE', `/solutions/${id}`)
}

/** 评论分页：一级评论（含回复预览）或 parent_id 指定回复页；includeDeleted 仅 admin */
export function listComments(query: {
  target_type: CommentTargetType
  target_id: string
  page?: number
  page_size?: number
  parent_id?: string
  include_deleted?: boolean
}): Promise<PageResult<CommentNode>> {
  return apiRequest('GET', `/comments${buildQuery(query)}`)
}

export function createComment(payload: CommentPayload): Promise<CommentNode> {
  return apiRequest('POST', '/comments', payload)
}

/** 软删评论（owner / admin） */
export function deleteComment(id: string): Promise<void> {
  return apiRequest('DELETE', `/comments/${id}`)
}

/** 举报（同目标 pending 重复 3003） */
export function createReport(payload: ReportPayload): Promise<void> {
  return apiRequest('POST', '/reports', payload)
}

// ---- 管理端（admin） ----

export function adminListSolutions(
  query: {
    page?: number
    page_size?: number
    status?: SolutionStatus
    keyword?: string
    problem_id?: string
  } = {},
): Promise<PageResult<AdminSolution>> {
  return apiRequest('GET', `/admin/solutions${buildQuery(query)}`)
}

/** 题解管理详情（按 id 直接打开预览） */
export function adminGetSolution(id: string): Promise<AdminSolution> {
  return apiRequest('GET', `/admin/solutions/${id}`)
}

/** 下架 / 恢复（removed ⇄ published） */
export function adminSetSolutionStatus(id: string, status: 'published' | 'removed'): Promise<void> {
  return apiRequest('PUT', `/admin/solutions/${id}/status`, { status })
}

/** 评论软删 / 恢复 */
export function adminSetCommentStatus(id: string, isDeleted: boolean): Promise<void> {
  return apiRequest('PUT', `/admin/comments/${id}/status`, { is_deleted: isDeleted })
}

/** 评论管理上下文（举报定位：评论 → 所属题解 target_id） */
export function adminGetComment(id: string): Promise<CommentAdminContext> {
  return apiRequest('GET', `/admin/comments/${id}`)
}

// ---- 代码广场（community.md code_shares）----

/** 代码广场分享分页（published；mine=true 返回本人全部状态，需登录） */
export function listCodeShares(
  query: {
    page?: number
    page_size?: number
    keyword?: string
    language?: CodeShareLanguage
    mine?: boolean
  } = {},
): Promise<PageResult<CodeShareSummary>> {
  return apiRequest('GET', `/codes${buildQuery(query)}`)
}

export function createCodeShare(payload: CodeSharePayload): Promise<CodeShareDetail> {
  return apiRequest('POST', '/codes', payload)
}

export function getCodeShare(id: string): Promise<CodeShareDetail> {
  return apiRequest('GET', `/codes/${id}`)
}

/** 下架自己的分享（软删；owner / admin） */
export function deleteCodeShare(id: string): Promise<void> {
  return apiRequest('DELETE', `/codes/${id}`)
}

// ---- 代码分享管理端（admin）----

export function adminListCodeShares(
  query: {
    page?: number
    page_size?: number
    status?: CodeShareStatus
    keyword?: string
    language?: CodeShareLanguage
  } = {},
): Promise<PageResult<AdminCodeShare>> {
  return apiRequest('GET', `/admin/codes${buildQuery(query)}`)
}

export function adminGetCodeShare(id: string): Promise<AdminCodeShare> {
  return apiRequest('GET', `/admin/codes/${id}`)
}

export function adminSetCodeShareStatus(
  id: string,
  status: 'published' | 'removed',
): Promise<void> {
  return apiRequest('PUT', `/admin/codes/${id}/status`, { status })
}
