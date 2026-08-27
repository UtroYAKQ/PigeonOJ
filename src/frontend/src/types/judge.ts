/**
 * 判题 / 提交模块类型（docs/contracts/judge.md）。
 */
import type { ProblemLanguage } from './problem'

export type SubmissionStatus =
  | 'pending'
  | 'judging'
  | 'accepted'
  | 'wrong_answer'
  | 'time_limit_exceeded'
  | 'memory_limit_exceeded'
  | 'output_limit_exceeded'
  | 'runtime_error'
  | 'compile_error'
  | 'system_error'

export interface Submission {
  id: string
  problem_id?: string
  language?: string
  submit_type?: string
  code?: string
  status: SubmissionStatus
  /** ACM 赛制比赛进行中为 null（restricted=true），赛后恢复数值 */
  score: number | null
  time_used_ms: number | null
  memory_used_kb: number | null
  error_message?: string | null
  created_at?: string
  cases?: SubmissionCaseResult[]
  /** ACM 赛制进行中：得分与测试点详情赛后公开 */
  restricted?: boolean
}

export interface SubmissionCaseResult {
  id: string
  case_name: string | null
  status: string
  time_used_ms: number | null
  memory_used_kb: number | null
  score: number | null
  output: string | null
}

export interface SubmissionListQuery {
  page?: number
  page_size?: number
  problem_id?: string
  status?: SubmissionStatus
}

/** 创建提交载荷（POST /submissions）；携带 invite_token 时为验题提交（submit_type=verify） */
export interface SubmissionCreatePayload {
  problem_id: string
  language: ProblemLanguage
  code: string
  invite_token?: string
}

/** 用户自测载荷（POST /problems/{id}/run-code）：单次运行，无测试点、不计分、不落库 */
export interface SelfTestPayload {
  problem_id: string
  language: ProblemLanguage
  code: string
  /** 自定义 stdin（可空） */
  input?: string
}

/** 用户自测结果：仅程序 stdout 与运行元信息（无比对、无期望输出） */
export interface SelfTestResult {
  status: SubmissionStatus | 'ok'
  output: string
  error_message: string | null
  time_used_ms: number
  memory_used_kb: number | null
}
