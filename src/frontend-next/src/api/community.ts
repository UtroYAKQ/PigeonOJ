/**
 * 社区模块 API（docs/contracts/community.md）：官方题解 / 题解分享 / 评论 / 举报 / 代码广场。
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

/** 官方题解（比赛进行中 3002；草稿题仅管理者可读） */
export function getEditorial(problemId: string): Promise<EditorialView> {
  return apiRequest('GET', `/problems/${problemId}/editorial`)
}

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

/** 评论分页：一级评论（含回复预览）或 parent_id 指定回复页 */
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

export function deleteComment(id: string): Promise<void> {
  return apiRequest('DELETE', `/comments/${id}`)
}

export function createReport(payload: ReportPayload): Promise<void> {
  return apiRequest('POST', '/reports', payload)
}

// ---- 代码广场 ----

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

export function deleteCodeShare(id: string): Promise<void> {
  return apiRequest('DELETE', `/codes/${id}`)
}

// ---- 管理端 ----

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

export function adminGetSolution(id: string): Promise<AdminSolution> {
  return apiRequest('GET', `/admin/solutions/${id}`)
}

export function adminSetSolutionStatus(
  id: string,
  status: 'published' | 'removed',
): Promise<void> {
  return apiRequest('PUT', `/admin/solutions/${id}/status`, { status })
}

export function adminSetCommentStatus(id: string, isDeleted: boolean): Promise<void> {
  return apiRequest('PUT', `/admin/comments/${id}/status`, { is_deleted: isDeleted })
}

export function adminGetComment(id: string): Promise<CommentAdminContext> {
  return apiRequest('GET', `/admin/comments/${id}`)
}

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