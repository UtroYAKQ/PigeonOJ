import { apiRequest } from './http'
import { buildQuery } from '@/utils/query'
import type {
  PageResult,
  SelfTestPayload,
  SelfTestResult,
  Submission,
  SubmissionCreatePayload,
  SubmissionListQuery,
} from '@/types'

export function createSubmission(
  body: SubmissionCreatePayload,
): Promise<{ submission_id: string; status: string }> {
  return apiRequest('POST', '/submissions', body)
}

export function listSubmissions(query: SubmissionListQuery = {}): Promise<PageResult<Submission>> {
  return apiRequest('GET', `/submissions${buildQuery(query)}`)
}
export function getSubmission(id: string): Promise<Submission> {
  return apiRequest('GET', `/submissions/${id}`)
}

/** 用户自测：经判题节点一次性运行，仅回传 stdout（docs/contracts/judge.md「用户自测」） */
export function runProblemCode(body: SelfTestPayload): Promise<SelfTestResult> {
  return apiRequest('POST', `/problems/${body.problem_id}/run-code`, {
    language: body.language,
    code: body.code,
    input: body.input ?? '',
  })
}
