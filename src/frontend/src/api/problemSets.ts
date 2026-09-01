import { apiRequest } from './http'
import { buildQuery } from '@/utils/query'
import type {
  PageResult,
  ProblemDetailEx,
  ProblemSetCreatePayload,
  ProblemSetDetail,
  ProblemSetEditPayload,
  ProblemSetItemsPayload,
  ProblemSetListQuery,
  ProblemSetSummary,
} from '@/types'

/** 题单中心：公开且未下线的全站题单（public） */
export function listProblemSets(
  query: ProblemSetListQuery = {},
): Promise<PageResult<ProblemSetSummary>> {
  return apiRequest('GET', `/problem-sets${buildQuery(query)}`)
}

/** 题单管理视图（admin/tutor）：全量题单，含私有与已下线，可叠加状态过滤 */
export function adminListProblemSets(
  query: ProblemSetListQuery & { status?: 'active' | 'archived' } = {},
): Promise<PageResult<ProblemSetSummary>> {
  return apiRequest('GET', `/admin/problem-sets${buildQuery(query)}`)
}

export function getProblemSet(id: string): Promise<ProblemSetDetail> {
  return apiRequest('GET', `/problem-sets/${id}`)
}

/** 创建题单（admin/tutor；团队题单随 teams 模块开放） */
export function createProblemSet(body: ProblemSetCreatePayload): Promise<ProblemSetSummary> {
  return apiRequest('POST', '/problem-sets', body)
}

/** 编辑题单元信息（title / description / visibility 缺省不动） */
export function updateProblemSet(
  id: string,
  body: ProblemSetEditPayload,
): Promise<ProblemSetSummary> {
  return apiRequest('PUT', `/problem-sets/${id}`, body)
}

/** 编排题目：全量替换题单内列表（题目须已发布公开；同题单内不得重复） */
export function replaceProblemSetItems(id: string, body: ProblemSetItemsPayload): Promise<null> {
  return apiRequest('PUT', `/problem-sets/${id}/items`, body)
}

/** 下线题单（status='archived'，不做物理删除） */
export function archiveProblemSet(id: string): Promise<ProblemSetSummary> {
  return apiRequest('POST', `/problem-sets/${id}/archive`)
}

/** 题单内题目详情（统一入口）：归属校验后返回与 GET /problems/{id} 一致的详情装配 */
export function getProblemSetProblem(
  setId: string,
  problemId: string,
): Promise<ProblemDetailEx> {
  return apiRequest('GET', `/problem-sets/${setId}/problems/${problemId}`)
}

/** 题单内交题：题单可见 + 题目属于该题单校验后走统一判题链路（返回与 POST /submissions 一致） */
export function createProblemSetSubmission(
  setId: string,
  problemId: string,
  body: { language: string; code: string },
): Promise<{ submission_id: string; status: string }> {
  return apiRequest('POST', `/problem-sets/${setId}/problems/${problemId}/submissions`, body)
}
