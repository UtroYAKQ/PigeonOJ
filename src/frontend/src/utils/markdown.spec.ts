import { describe, expect, it } from 'vitest'

import { renderMarkdown } from './markdown'

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
