import { createApp, h } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import MarkdownEditor from './MarkdownEditor.vue'

describe('MarkdownEditor', () => {
  it('does not submit a surrounding form when editing or toggling preview', () => {
    const onSubmit = vi.fn()
    const host = document.createElement('div')
    document.body.appendChild(host)

    const app = createApp({
      render: () =>
        h(
          'form',
          {
            onSubmit: (event: Event) => {
              event.preventDefault()
              onSubmit()
            },
          },
          [h(MarkdownEditor, { modelValue: '' })],
        ),
    })
    app.use(i18n)
    app.mount(host)

    const buttons = [...host.querySelectorAll('button')]
    expect(buttons.length).toBeGreaterThan(0)
    expect(buttons.every((button) => button.type === 'button')).toBe(true)

    buttons[buttons.length - 1]!.click()
    expect(onSubmit).not.toHaveBeenCalled()

    app.unmount()
    host.remove()
  })
})
