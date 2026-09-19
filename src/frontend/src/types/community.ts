/**
 * 社区模块类型（docs/contracts/community.md）：题解 / 评论 / 举报。
 */

/** 作者摘要（题解 / 评论公共） */
export interface CommunityAuthor {
  id: string
  nickname: string
  avatar_url?: string | null
}

/** 题目摘要（管理列表定位用） */
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

/** 题解列表项（excerpt = 正文前 200 字符） */
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

/** 题解详情（含正文全文） */
export interface SolutionDetail extends SolutionSummary {
  content: string
}

/** 题解管理列表项（全状态） */
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
  /** 仅一级评论携带：未删回复数与前 2 条预览 */
  reply_count: number
  replies: CommentNode[]
}

/** 创建 / 编辑题解载荷（创建即发布，无草稿态） */
export interface SolutionPayload {
  title: string
  content: string
}

/** 评论目标类型（community.md comments：solution / code_share 开放） */
export type CommentTargetType = 'solution' | 'code_share'

/** 发表评论 / 回复载荷 */
export interface CommentPayload {
  target_type: CommentTargetType
  target_id: string
  parent_id?: string
  content: string
}

/** 举报载荷（community.md reports） */
export interface ReportPayload {
  target_type: 'problem' | 'solution' | 'code_share' | 'post' | 'comment' | 'user'
  target_id: string
  reason: string
}

// ---- 代码广场（community.md code_shares）----

export type CodeShareLanguage = 'cpp17' | 'python3.12' | 'java21'
export type CodeShareStatus = 'published' | 'removed'

/** 代码分享列表项（说明截断摘要；关联题目摘要随行） */
export interface CodeShareSummary {
  id: string
  author: CommunityAuthor
  title: string
  language: CodeShareLanguage
  description_excerpt: string
  status: CodeShareStatus
  created_at: string
  updated_at: string
}

/** 代码分享详情（含代码原文与完整说明） */
export interface CodeShareDetail extends CodeShareSummary {
  description: string | null
  code: string
}

/** 代码分享管理列表项（code 不回传，预览走详情端点） */
export interface AdminCodeShare {
  id: string
  author: CommunityAuthor
  title: string
  language: CodeShareLanguage
  excerpt: string
  status: CodeShareStatus
  created_at: string
  updated_at: string
}

/** 发布代码分享载荷 */
export interface CodeSharePayload {
  title: string
  language: CodeShareLanguage
  code: string
  description?: string
}

/** 评论管理上下文（举报定位：评论 → 所属题解） */
export interface CommentAdminContext {
  id: string
  target_type: string
  target_id: string
  content: string | null
  is_deleted: boolean
  created_at: string
}
