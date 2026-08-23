import { apiRequest } from './request'
import type {
  PageResult,
  ProblemLanguage,
  Submission,
  SubmissionCreatePayload,
  SubmissionListQuery,
} from '@/types'

export function createSubmission(body: SubmissionCreatePayload): Promise<{ submission_id: string; status: string }> {
  return apiRequest('POST', '/submissions', body)
}

export function listSubmissions(query: SubmissionListQuery = {}): Promise<PageResult<Submission>> {
  const params = new URLSearchParams()
  if (query.page) params.set('page', String(query.page))
  if (query.page_size) params.set('page_size', String(query.page_size))
  if (query.problem_id) params.set('problem_id', query.problem_id)
  if (query.status) params.set('status', query.status)
  const qs = params.toString()
  return apiRequest('GET', `/submissions${qs ? `?${qs}` : ''}`)
}
export function getSubmission(id: string): Promise<Submission> { return apiRequest('GET', `/submissions/${id}`) }
