/**
 * Markdown 渲染：题面 / 输入输出说明 / 题解均为 Markdown（docs/contracts/problems.md 数据模型）。
 * html: false 使原始 HTML 按文本转义，输出再经 DOMPurify 白名单过滤，双重防 XSS。
 */
import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({ html: false, linkify: true, breaks: false })

export function renderMarkdown(source: string | null | undefined): string {
  if (!source) return ''
  return DOMPurify.sanitize(md.render(source), {
    ALLOWED_ATTR: ['href', 'title', 'alt', 'src', 'class'],
    FORBID_TAGS: ['style', 'form', 'input', 'iframe', 'script'],
  })
}
