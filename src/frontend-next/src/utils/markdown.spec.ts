import { describe, expect, it } from 'vitest'

import { renderCommentMarkdown, renderMarkdown } from './markdown'

describe('utils/markdown（渲染 + 净化）', () => {
  it('行内公式渲染为 KaTeX', () => {
    const html = renderMarkdown('数据范围为 $1 \\le n \\le 10^9$')
    expect(html).toContain('katex')
  })

  it('块级公式渲染为 KaTeX display', () => {
    const html = renderMarkdown('$$c = \\pm\\sqrt{a^2 + b^2}$$')
    expect(html).toContain('katex-display')
  })

  it('KaTeX 输出的 style / aria-hidden 属性不被剥离', () => {
    const html = renderMarkdown('$x$')
    expect(html).toContain('aria-hidden')
    expect(html).toMatch(/style="/)
  })

  it('原始 HTML 被转义（html:false）', () => {
    const html = renderMarkdown('<b>hi</b>')
    expect(html).not.toContain('<b>')
    expect(html).toContain('&lt;b&gt;')
  })

  it('script 标签被剥离', () => {
    const html = renderMarkdown('hello <script>alert(1)</script>')
    expect(html).not.toContain('<script')
  })

  it('图片与链接属性保留', () => {
    const html = renderMarkdown('[t](https://a.b) ![p](/api/v1/files/x)')
    expect(html).toContain('href="https://a.b"')
    expect(html).toContain('src="/api/v1/files/x"')
  })
})
describe('utils/markdown（评论渲染）', () => {
  it('站内图片保留并带评论样式类', () => {
    const html = renderCommentMarkdown('![p](/api/v1/files/2026/11/a.png)')
    expect(html).toContain('src="/api/v1/files/2026/11/a.png"')
    expect(html).toContain('class="comment-image"')
  })

  it('外部图片退回 alt 文本，不渲染 img', () => {
    const html = renderCommentMarkdown('![外部图](https://evil.test/a.png)')
    expect(html).not.toContain('<img')
    expect(html).toContain('外部图')
  })

  it('基础 Markdown 渲染与链接加固', () => {
    const html = renderCommentMarkdown('**粗体** [链接](https://a.b)')
    expect(html).toContain('<strong>粗体</strong>')
    expect(html).toContain('target="_blank"')
    expect(html).toContain('rel="noopener noreferrer nofollow"')
  })

  it('脚本不会注入', () => {
    const html = renderCommentMarkdown('<script>alert(1)</script>')
    expect(html).not.toContain('<script')
  })
})
