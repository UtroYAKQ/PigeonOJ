/**
 * 判题 / 提交模块类型（docs/contracts/judge.md）。
 */
import type { ProblemLanguage } from './problem'

export type SubmissionStatus = 'pending' | 'judging' | 'accepted' | 'wrong_answer' | 'time_limit_exceeded' | 'memory_limit_exceeded' | 'output_limit_exceeded' | 'runtime_error' | 'compile_error' | 'system_error'

export interface Submission {
  id: string
  problem_id?: string
  language?: string
  submit_type?: string
  code?: string
  status: SubmissionStatus
  score: number
  time_used_ms: number | null
  memory_used_kb: number | null
  error_message?: string | null
  created_at?: string
  cases?: SubmissionCaseResult[]
}

export interface SubmissionCaseResult {
  id: string
  case_name: string | null
  status: string
  time_used_ms: number | null
  memory_used_kb: number | null
  score: number
  output: string | null
}

export interface SubmissionListQuery {
  page?: number
  page_size?: number
  problem_id?: string
  status?: SubmissionStatus
}

/** 创建提交载荷（POST /submissions） */
export interface SubmissionCreatePayload {
  problem_id: string
  language: ProblemLanguage
  code: string
}
