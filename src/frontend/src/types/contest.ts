/**
 * 比赛模块类型（docs/contracts/contests.md）。
 * 团队比赛（contest_type='team'）随 teams 模块开放，当前接口不产生。
 */
import type { SubmissionStatus } from './judge'

export type ContestRuleType = 'ACM' | 'IOI'
export type ContestStatusType = 'scheduled' | 'running' | 'finished'
export type RegistrationStatusType = 'registered' | 'cancelled'

/** 比赛题目编排项（letter 自动分配；score 为 IOI 单题分值） */
export interface ContestProblemPayload {
  problem_id: string
  score?: number
}

export interface ContestCreatePayload {
  title: string
  description?: string | null
  /** 比赛头像 URL（/files/upload/image 上传后的公开地址） */
  logo?: string | null
  rule_type: ContestRuleType
  start_time: string
  end_time: string
  register_start_time: string
  register_end_time: string
  freeze_offset_seconds?: number
  problems?: ContestProblemPayload[]
}

/** 编辑比赛（缺省不动；problems 传即全量重排） */
export interface ContestEditPayload {
  title?: string
  description?: string | null
  logo?: string | null
  rule_type?: ContestRuleType
  start_time?: string
  end_time?: string
  register_start_time?: string
  register_end_time?: string
  freeze_offset_seconds?: number
  problems?: ContestProblemPayload[] | null
}

export interface ContestProblemItem {
  problem_id: string
  letter?: string | null
  score: number
  sort_order: number
  title: string
  difficulty?: number | null
}

export interface ContestSummary {
  id: string
  title: string
  description?: string | null
  logo?: string | null
  contest_type: 'public' | 'team'
  rule_type: ContestRuleType
  start_time: string
  end_time: string
  register_start_time: string
  register_end_time: string
  freeze_offset_seconds: number
  board_frozen: boolean
  status: ContestStatusType
  problem_count: number
  registered_count: number
  created_at: string
  updated_at: string
}

/** 比赛详情：报名状态与时间窗口能力位；题目仅在看题窗口内携带 */
export interface ContestDetail extends ContestSummary {
  my_registration?: RegistrationStatusType | null
  can_register: boolean
  can_view_problems: boolean
  can_submit: boolean
  can_manage: boolean
  problems: ContestProblemItem[]
}

/** 榜单单题格子（is_frozen=true 表示封榜快照；problem_score 为该题满分，用于分母） */
export interface BoardCell {
  problem_id: string
  letter?: string | null
  problem_score: number
  accepted: boolean
  attempts: number
  penalty: number
  score: number
  is_frozen: boolean
  accepted_at?: string | null
}

export interface BoardRow {
  rank: number
  user_id: string
  nickname: string
  solved: number
  total_penalty: number
  total_score: number
  cells: BoardCell[]
}

export interface Board {
  contest_id: string
  rule_type: ContestRuleType
  board_frozen: boolean
  rows: BoardRow[]
}

export interface MyContestItem extends ContestSummary {
  my_registration: RegistrationStatusType
}

/** 比赛提交记录列表项（比赛期间隐藏，赛后开放；行可点开详情） */
export interface ContestSubmissionItem {
  id: string
  problem_id: string
  letter?: string | null
  language: string
  status: SubmissionStatus
  score: number | null
  time_used_ms: number | null
  memory_used_kb: number | null
  nickname: string
  created_at: string
}

export interface ContestListQuery {
  page?: number
  page_size?: number
  status?: ContestStatusType
  /** 名称关键字（模糊匹配） */
  keyword?: string
}
