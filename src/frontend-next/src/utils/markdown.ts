/**
 * Markdown 渲染：题面 / 输入输出说明 / 题解均为 Markdown（docs/contracts/problems.md 数据模型）。
 * html: false 使原始 HTML 按文本转义，输出再经 DOMPurify 白名单过滤，双重防 XSS。
 * 数学公式经 @vscode/markdown-it-katex 渲染（$...$ 行内 / $$...$$ 块级），与编辑器预览能力对齐。
 */
import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'
import katexPlugin from '@vscode/markdown-it-katex'

import { siteImageUrl } from './image'

const md = new MarkdownIt({ html: false, linkify: true, breaks: false }).use(katexPlugin)

interface ImageToken {
  attrGet(name: string): unknown
  attrSet(name: string, value: string): void
}

/** 站内插图走 960 档缩略图，并延迟解码，避免长题面里的图片阻塞首屏渲染 */
function applyImageAttrs(token: ImageToken): void {
  const src = token.attrGet('src')
  if (src) token.attrSet('src', siteImageUrl(String(src), 960))
  token.attrSet('loading', 'lazy')
  token.attrSet('decoding', 'async')
}

const defaultMdImage = md.renderer.rules.image
  ?? ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options))

md.renderer.rules.image = (tokens, idx, options, env, self) => {
  applyImageAttrs(tokens[idx])
  return defaultMdImage(tokens, idx, options, env, self)
}

export function renderMarkdown(source: string | null | undefined): string {
  if (!source) return ''
  return DOMPurify.sanitize(md.render(source), {
    // style / aria-hidden / encoding 为 KaTeX 输出所需（html:false 下输出标签均来自可信插件）
    ALLOWED_ATTR: ['href', 'title', 'alt', 'src', 'class', 'style', 'aria-hidden', 'encoding', 'loading', 'decoding'],
    FORBID_TAGS: ['style', 'form', 'input', 'iframe', 'script'],
  })
}
/**
 * 评论内容渲染：完整 Markdown（与所见即所得编辑器一致），但图片只允许本站上传地址，
 * 外部图床一律退回 alt 文本，避免渲染不可信资源。
 */
const SITE_IMAGE_RE = /^\/api\/v1\/files\/[A-Za-z0-9_./-]+$/

const commentMd = new MarkdownIt({ html: false, linkify: true, breaks: true })

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const defaultImage = commentMd.renderer.rules.image
  ?? ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options))

commentMd.renderer.rules.image = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  const src = String(token.attrGet('src') ?? '')
  if (!SITE_IMAGE_RE.test(src))
    return escapeHtml(String(token.content))
  token.attrSet('class', 'comment-image')
  applyImageAttrs(token)
  return defaultImage(tokens, idx, options, env, self)
}

const defaultLinkOpen = commentMd.renderer.rules.link_open
  ?? ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options))

commentMd.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  tokens[idx].attrSet('target', '_blank')
  tokens[idx].attrSet('rel', 'noopener noreferrer nofollow')
  return defaultLinkOpen(tokens, idx, options, env, self)
}

export function renderCommentMarkdown(source: string | null | undefined): string {
  if (!source) return ''
  return DOMPurify.sanitize(commentMd.render(source), {
    ALLOWED_ATTR: ['href', 'title', 'alt', 'src', 'class', 'target', 'rel', 'loading', 'decoding'],
    FORBID_TAGS: ['style', 'form', 'input', 'iframe', 'script'],
  })
}
