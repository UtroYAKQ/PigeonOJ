import { apiRequest } from './http'
import { buildQuery } from '@/utils/query'
import type {
  Board,
  ContestCreatePayload,
  ContestDetail,
  ContestEditPayload,
  ContestListQuery,
  ContestProblemItem,
  ContestSubmissionItem,
  ContestSummary,
  MyContestItem,
  PageResult,
  Submission,
} from '@/types'

/** 比赛中心：公开比赛（可按状态过滤） */
export function listContests(query: ContestListQuery = {}): Promise<PageResult<ContestSummary>> {
  return apiRequest('GET', `/contests${buildQuery(query)}`)
}

/** 我的比赛（我报名的比赛 + 报名状态） */
export function listMyContests(query: ContestListQuery = {}): Promise<PageResult<MyContestItem>> {
  return apiRequest('GET', `/contests/me${buildQuery(query)}`)
}

export function getContest(id: string): Promise<ContestDetail> {
  return apiRequest('GET', `/contests/${id}`)
}

/** 创建比赛（admin/tutor） */
export function createContest(body: ContestCreatePayload): Promise<ContestSummary> {
  return apiRequest('POST', '/contests', body)
}

/** 编辑比赛（缺省不动；problems 传即全量重排） */
export function updateContest(id: string, body: ContestEditPayload): Promise<ContestSummary> {
  return apiRequest('PUT', `/contests/${id}`, body)
}

/** 报名（重复 3003，截止 3002） */
export function registerContest(id: string): Promise<null> {
  return apiRequest('POST', `/contests/${id}/register`)
}

/** 比赛题目列表（已报名 + 开赛后） */
export function listContestProblems(id: string): Promise<ContestProblemItem[]> {
  return apiRequest('GET', `/contests/${id}/problems`)
}

/** 编排页题目搜索（统一入口）：公开题 + 本人私有题（已发布），仅比赛管理角色 */
export function searchContestProblems(
  contestId: string,
  query: { keyword?: string; page?: number; page_size?: number } = {},
): Promise<PageResult<ContestProblemItem>> {
  return apiRequest('GET', `/contests/${contestId}/problems/search${buildQuery(query)}`)
}

/** 比赛内题目详情（统一入口）：与题库详情装配一致 */
export function getContestProblem(
  contestId: string,
  problemId: string,
): Promise<import('@/types').ProblemDetailEx> {
  return apiRequest('GET', `/contests/${contestId}/problems/${problemId}`)
}

/** 比赛交题（统一入口）：窗口校验后落 contest 提交；赛后自动补题标记 */
export function createContestSubmission(
  contestId: string,
  problemId: string,
  body: { language: string; code: string },
): Promise<{ submission_id: string; status: string }> {
  return apiRequest('POST', `/contests/${contestId}/problems/${problemId}/submissions`, body)
}

/** 榜单（封榜时按冻结快照展示） */
export function getContestBoard(id: string): Promise<Board> {
  return apiRequest('GET', `/contests/${id}/board`)
}

/** 比赛提交记录（管理角色随时可见，参赛者赛后开放）；
 * keyword 模糊匹配提交人昵称，language / status / problem_id 精确过滤 */
export function listContestSubmissions(
  id: string,
  query: {
    page?: number
    page_size?: number
    keyword?: string
    language?: string
    status?: string
    problem_id?: string
  } = {},
): Promise<PageResult<ContestSubmissionItem>> {
  return apiRequest('GET', `/contests/${id}/submissions${buildQuery(query)}`)
}

/** 比赛提交详情（统一入口：窗口校验后复用判题详情装配） */
export function getContestSubmission(contestId: string, submissionId: string): Promise<Submission> {
  return apiRequest('GET', `/contests/${contestId}/submissions/${submissionId}`)
}

/** 榜单单格成功提交（赛后开放）：该 (选手, 题目) 比赛内的 AC 提交列表 */
export function listContestCellAccepted(
  contestId: string,
  userId: string,
  problemId: string,
): Promise<ContestSubmissionItem[]> {
  return apiRequest('GET', `/contests/${contestId}/board/${userId}/${problemId}/accepted`)
}

/** 手动解冻榜单（admin/tutor）：从 submissions 重算并回填封榜期结果 */
export function unfreezeContestBoard(id: string): Promise<ContestSummary> {
  return apiRequest('POST', `/contests/${id}/unfreeze`)
}
