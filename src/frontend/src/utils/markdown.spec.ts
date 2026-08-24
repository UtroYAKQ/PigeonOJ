import { describe, expect, it } from 'vitest'

import { renderMarkdown } from './markdown'

describe('renderMarkdown', () => {
  it('空值返回空串', () => {
    expect(renderMarkdown(null)).toBe('')
    expect(renderMarkdown(undefined)).toBe('')
    expect(renderMarkdown('')).toBe('')
  })

  it('渲染基础 Markdown 结构', () => {
    const html = renderMarkdown('# 标题\n\n- 项目')
    expect(html).toContain('<h1>标题</h1>')
    expect(html).toContain('<ul>')
    expect(html).toContain('<li>项目</li>')
  })

  it('原始 HTML 被转义为文本（markdown-it html:false）', () => {
    const html = renderMarkdown('<script>alert(1)</script>')
    expect(html).not.toContain('<script>')
    // html:false 下标签按文本展示，< > 已转义
    expect(html).toContain('&lt;script&gt;')
  })

  it('危险标签与事件属性被 DOMPurify 过滤', () => {
    const html = renderMarkdown(
      '<iframe src="https://evil.example"></iframe>\n\n<style>body{}</style>',
    )
    expect(html).not.toContain('<iframe')
    expect(html).not.toContain('<style')
    // javascript: 协议不生成链接（markdown-it 内置协议校验，按转义文本展示）
    const html2 = renderMarkdown('[x](javascript:alert(1))')
    expect(html2).not.toContain('<a ')
  })

  it('链接自动识别（linkify）且仅保留白名单属性', () => {
    const html = renderMarkdown('visit https://example.com now')
    expect(html).toContain('<a href="https://example.com"')
  })
})
