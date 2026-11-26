import { createApp, h, nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import MarkdownView from './MarkdownView.vue'

describe('MarkdownView', () => {
  it('highlights fenced code blocks with shiki tokens', async () => {
    const host = document.createElement('div')
    document.body.appendChild(host)
    const app = createApp({
      render: () =>
        h(MarkdownView, {
          source: '```cpp\nint main() { return 0; }\n```',
        }),
    })
    app.mount(host)
    await nextTick()

    await vi.waitFor(
      () => {
        expect(host.querySelectorAll('.shiki-token').length).toBeGreaterThan(0)
      },
      { timeout: 15000, interval: 50 },
    )
    expect(host.querySelector('.shiki-token')?.getAttribute('style')).toContain('--shiki-light')

    app.unmount()
    host.remove()
  })
})