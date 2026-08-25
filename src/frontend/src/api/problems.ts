import { apiRequest } from './http'
import { buildQuery } from '@/utils/query'
import type {
  PageResult,
  ProblemCreatePayload,
  ProblemDetailEx,
  ProblemEditPayload,
  ProblemLanguage,
  ProblemListQuery,
  ProblemSummary,
  ProblemTagItem,
  ProblemTestCase,
  TestCaseDraft,
  TestCaseUpsertPayload,
} from '@/types'

export function listProblems(query: ProblemListQuery = {}): Promise<PageResult<ProblemSummary>> {
  return apiRequest('GET', `/problems${buildQuery(query)}`)
}

/** 激活标签列表（public：打标选择器与题库筛选） */
export function listActiveTags(): Promise<ProblemTagItem[]> {
  return apiRequest('GET', '/problems/tags')
}
export function getProblem(id: string): Promise<ProblemDetailEx> {
  return apiRequest('GET', `/problems/${id}`)
}
export function createProblem(body: ProblemCreatePayload): Promise<ProblemSummary> {
  return apiRequest('POST', '/problems', body)
}
export function updateProblem(id: string, body: ProblemEditPayload): Promise<ProblemSummary> {
  return apiRequest('PUT', `/problems/${id}`, body)
}
export function replaceTestCases(id: string, cases: TestCaseDraft[]): Promise<null> {
  return apiRequest('PUT', `/problems/${id}/test-cases`, { cases })
}

/** 增量更新测试点：只提交变化的行（带 id=修改，内容留空=不变；无 id=新增；delete_ids=删除）。响应为服务器权威全量列表 */
export function patchTestCases(
  id: string,
  body: { upserts: TestCaseUpsertPayload[]; delete_ids: string[] },
): Promise<{ cases: ProblemTestCase[] }> {
  return apiRequest('PATCH', `/problems/${id}/test-cases`, body)
}

/** 全量替换展示样例（存 problems.samples，不参与判题；≤10 组、单项各 ≤64KB） */
export function replaceSamples(
  id: string,
  samples: Array<{ input: string; output: string }>,
): Promise<null> {
  return apiRequest('PUT', `/problems/${id}/samples`, { samples })
}
export function publishProblem(id: string): Promise<ProblemSummary> {
  return apiRequest('POST', `/problems/${id}/publish`)
}
export function archiveProblem(id: string): Promise<ProblemSummary> {
  return apiRequest('POST', `/problems/${id}/archive`)
}
export function initVerification(
  id: string,
  body: { invite_expires_hours?: number },
): Promise<{
  verification_id: string
  invite?: { token: string; expires_at: string | null }
}> {
  return apiRequest('POST', `/problems/${id}/verify`, body)
}
export function resolveVerifyInvite(
  token: string,
): Promise<{
  problem_id: string
  problem_title: string
  expires_at: string | null
  description: string
  input_description?: string | null
  output_description?: string | null
  tags: string[]
  time_limit_ms: number
  memory_limit_mb: number
  samples: Array<{ name: string; input: string; output: string }>
}> {
  return apiRequest('GET', `/verify-invites/${token}`)
}

/** 提交验题代码：存在进行中验题时任意登录用户可提交（invite_token 可选） */
export function submitVerifyCode(
  id: string,
  body: { code: string; language: ProblemLanguage; invite_token?: string },
): Promise<{ submission_id: string; status: string }> {
  return apiRequest('POST', `/problems/${id}/verify`, body)
}
