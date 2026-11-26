/**
 * Markdown 渲染：题面 / 输入输出说明 / 题解均为 Markdown（docs/contracts/problems.md 数据模型）。
 * html: false 使原始 HTML 按文本转义，输出再经 DOMPurify 白名单过滤，双重防 XSS。
 * 数学公式经 @vscode/markdown-it-katex 渲染（$...$ 行内 / $$...$$ 块级），与编辑器预览能力对齐。
 */
import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'
import katexPlugin from '@vscode/markdown-it-katex'

const md = new MarkdownIt({ html: false, linkify: true, breaks: false }).use(katexPlugin)

export function renderMarkdown(source: string | null | undefined): string {
  if (!source) return ''
  return DOMPurify.sanitize(md.render(source), {
    // style / aria-hidden / encoding 为 KaTeX 输出所需（html:false 下输出标签均来自可信插件）
    ALLOWED_ATTR: ['href', 'title', 'alt', 'src', 'class', 'style', 'aria-hidden', 'encoding'],
    FORBID_TAGS: ['style', 'form', 'input', 'iframe', 'script'],
  })
}
