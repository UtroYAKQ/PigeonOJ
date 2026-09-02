import { apiRequest } from './http'
import { buildQuery } from '@/utils/query'
import type {
  PageResult,
  ProblemCreatePayload,
  ProblemDetailEx,
  ProblemEditPayload,
  ProblemLanguage,
  ProblemListQuery,
  ProblemSubmissionItem,
  ProblemSummary,
  ProblemTagItem,
  ProblemTestCase,
  Submission,
  TestCaseDraft,
  TestCaseUpsertPayload,
} from '@/types'

export function listProblems(query: ProblemListQuery = {}): Promise<PageResult<ProblemSummary>> {
  return apiRequest('GET', `/problems${buildQuery(query)}`)
}

/** 题目管理视角：该题全员提交列表（创建者与管理角色，docs/contracts/judge.md）；
 * keyword 模糊匹配提交人昵称，language / status / submit_type 精确过滤 */
export function listProblemSubmissions(
  id: string,
  query: {
    page?: number
    page_size?: number
    status?: string
    keyword?: string
    language?: string
    submit_type?: string
  } = {},
): Promise<PageResult<ProblemSubmissionItem>> {
  return apiRequest('GET', `/problems/${id}/submissions${buildQuery(query)}`)
}

/** 题目管理视角：提交详情（统一入口，管理权限 + 归属校验后复用判题装配） */
export function getProblemSubmission(problemId: string, submissionId: string): Promise<Submission> {
  return apiRequest('GET', `/problems/${problemId}/submissions/${submissionId}`)
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

/** 显式生效：把已通过验题的暂存集晋升为生效集（验题与晋升解耦；点「保存」才生效） */
export function applyTestCases(id: string): Promise<ProblemSummary> {
  return apiRequest('POST', `/problems/${id}/test-cases/apply`)
}

/** 增量更新测试点：只提交变化的行（带 id=修改，input/expected_output 缺省或 null=内容不变、空字符串=清空该侧；无 id=新增；delete_ids=删除）。响应为服务器权威全量列表 */
export function patchTestCases(
  id: string,
  body: { upserts: TestCaseUpsertPayload[]; delete_ids: string[] },
): Promise<{ cases: ProblemTestCase[] }> {
  return apiRequest('PATCH', `/problems/${id}/test-cases`, body)
}

/** 全量替换展示样例（存 problems.samples，不参与判题；≤10 组、单项各 ≤64KB，explanation 选填） */
export function replaceSamples(
  id: string,
  samples: Array<{ input: string; output: string; explanation?: string }>,
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
export function resolveVerifyInvite(token: string): Promise<{
  problem_id: string
  problem_title: string
  expires_at: string | null
  background: string
  description: string
  input_description?: string | null
  output_description?: string | null
  note?: string | null
  tags: string[]
  time_limit_ms: number
  memory_limit_mb: number
  samples: Array<{ name: string; input: string; output: string; explanation?: string }>
}> {
  return apiRequest('GET', `/verify-invites/${token}`)
}

/** 查询题目当前有效的验题邀请链接；无或已失效返回 null */
export function getVerifyInvite(
  id: string,
): Promise<{ token: string; expires_at: string | null } | null> {
  return apiRequest('GET', `/problems/${id}/verify/invite`)
}

/** 提交验题代码：存在进行中验题时任意登录用户可提交（invite_token 可选） */
export function submitVerifyCode(
  id: string,
  body: { code: string; language: ProblemLanguage; invite_token?: string },
): Promise<{ submission_id: string; status: string }> {
  return apiRequest('POST', `/problems/${id}/verify`, body)
}
