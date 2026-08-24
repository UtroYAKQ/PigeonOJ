import { apiRequest } from './request'
import type {
  PageResult,
  ProblemCreatePayload,
  ProblemDetailEx,
  ProblemDifficulty,
  ProblemEditPayload,
  ProblemLanguage,
  ProblemListQuery,
  ProblemSummary,
  TestCaseDraft,
} from '@/types'

export function listProblems(query: ProblemListQuery = {}): Promise<PageResult<ProblemSummary>> {
  const params = new URLSearchParams()
  if (query.page) params.set('page', String(query.page))
  if (query.page_size) params.set('page_size', String(query.page_size))
  if (query.difficulty) params.set('difficulty', query.difficulty)
  if (query.keyword) params.set('keyword', query.keyword)
  if (query.tag) params.set('tag', query.tag)
  if (query.scope && query.scope !== 'all') params.set('scope', query.scope)
  if (query.status) params.set('status', query.status)
  const qs = params.toString()
  return apiRequest('GET', `/problems${qs ? `?${qs}` : ''}`)
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
export function publishProblem(id: string): Promise<ProblemSummary> {
  return apiRequest('POST', `/problems/${id}/publish`)
}
export function archiveProblem(id: string): Promise<ProblemSummary> {
  return apiRequest('POST', `/problems/${id}/archive`)
}
export function initVerification(
  id: string,
  body: { verifier_id?: string; invite_expires_hours?: number },
): Promise<{
  verification_id: string
  invite?: { token: string; expires_at: string | null }
  verifier_id?: string
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
  difficulty: ProblemDifficulty
  time_limit_ms: number
  memory_limit_mb: number
  samples: Array<{ id: string; name: string; input: string; output: string }>
}> {
  return apiRequest('GET', `/verify-invites/${token}`)
}

/** 自行验题：以当前账号提交验题代码（须存在 verifier_id=自己的进行中验题） */
export function submitVerifyCode(
  id: string,
  body: { code: string; language: ProblemLanguage },
): Promise<{ submission_id: string; status: string }> {
  return apiRequest('POST', `/problems/${id}/verify`, body)
}
