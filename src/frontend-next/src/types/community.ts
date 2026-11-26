/**
 * 社区模块类型（docs/contracts/community.md）：题解 / 评论 / 举报 / 代码广场。
 */

export interface CommunityAuthor {
  id: string
  nickname: string
  avatar_url?: string | null
}

export interface CommunityProblemBrief {
  id: string
  title: string
}

/** 官方题解浏览视图（GET /problems/{id}/editorial） */
export interface EditorialView {
  solution: string | null
  can_manage: boolean
}

export type SolutionStatus = 'published' | 'removed'

export interface SolutionSummary {
  id: string
  problem_id: string
  author: CommunityAuthor
  title: string
  excerpt: string
  status: SolutionStatus
  comment_count: number
  created_at: string
  updated_at: string
}

export interface SolutionDetail extends SolutionSummary {
  content: string
}

export interface AdminSolution {
  id: string
  problem: CommunityProblemBrief
  author: CommunityAuthor
  title: string
  excerpt: string
  status: SolutionStatus
  comment_count: number
  created_at: string
  updated_at: string
}

/** 评论输出（软删占位：content / author 为 null） */
export interface CommentNode {
  id: string
  parent_id: string | null
  content: string | null
  author: CommunityAuthor | null
  is_deleted: boolean
  created_at: string
  reply_count: number
  replies: CommentNode[]
}

export interface SolutionPayload {
  title: string
  content: string
}

export type CommentTargetType = 'solution' | 'code_share'

export interface CommentPayload {
  target_type: CommentTargetType
  target_id: string
  parent_id?: string
  content: string
}

export type ReportTargetType = 'problem' | 'solution' | 'code_share' | 'post' | 'comment' | 'user'

export interface ReportPayload {
  target_type: ReportTargetType
  target_id: string
  reason: string
}

export type CodeShareLanguage = 'cpp17' | 'python3.12' | 'java21'
export type CodeShareStatus = 'published' | 'removed'

export interface CodeShareSummary {
  id: string
  author: CommunityAuthor
  title: string
  language: CodeShareLanguage
  /** 关联题目（可空；比赛进行中该关联分享被过滤 / 拒绝） */
  problem_id?: string | null
  description_excerpt: string
  status: CodeShareStatus
  created_at: string
  updated_at: string
}

export interface CodeShareDetail extends CodeShareSummary {
  description: string | null
  code: string
}

export interface AdminCodeShare {
  id: string
  author: CommunityAuthor
  title: string
  language: CodeShareLanguage
  problem_id?: string | null
  excerpt: string
  status: CodeShareStatus
  created_at: string
  updated_at: string
}

export interface CodeSharePayload {
  title: string
  language: CodeShareLanguage
  code: string
  description?: string
  problem_id?: string
}

export interface CommentAdminContext {
  id: string
  target_type: string
  target_id: string
  content: string | null
  is_deleted: boolean
  created_at: string
}