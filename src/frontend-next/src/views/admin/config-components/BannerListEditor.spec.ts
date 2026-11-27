import { createApp, h, nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/api/files', () => ({ uploadImage: vi.fn() }))
vi.mock('@/utils/feedback', () => ({
  message: { warning: vi.fn(), error: vi.fn(), success: vi.fn() },
}))

import BannerListEditor from './BannerListEditor.vue'

function mountInForm() {
  const host = document.createElement('div')
  document.body.appendChild(host)
  let submits = 0
  const app = createApp({
    render: () =>
      h(
        'form',
        {
          onSubmit: (event: Event) => {
            event.preventDefault()
            submits += 1
          },
        },
        h(BannerListEditor),
      ),
  })
  app.mount(host)
  return {
    host,
    submits: () => submits,
    unmount: () => {
      app.unmount()
      host.remove()
    },
  }
}

describe('BannerListEditor', () => {
  it('adds a banner without submitting the surrounding config form', async () => {
    const { host, submits, unmount } = mountInForm()
    const addButton = [...host.querySelectorAll('button')].find((button) =>
      button.textContent?.includes('config.addBanner'),
    )

    expect(addButton?.getAttribute('type')).toBe('button')
    addButton!.click()
    await nextTick()

    expect(submits()).toBe(0)
    expect(host.querySelectorAll('input').length).toBeGreaterThan(0)
    unmount()
  })
})