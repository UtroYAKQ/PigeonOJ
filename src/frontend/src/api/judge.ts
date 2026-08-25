import { apiRequest } from './http'
import { buildQuery } from '@/utils/query'
import type { PageResult, Submission, SubmissionCreatePayload, SubmissionListQuery } from '@/types'

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
