import { createApp, nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'

vi.mock('vue-i18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }))
vi.mock('@/utils/feedback', () => ({ message: { warning: vi.fn(), error: vi.fn() } }))

import UserEmailPicker from './UserEmailPicker.vue'
import type { UserCandidate } from '@/types'

function mountPicker(search: (email: string) => Promise<UserCandidate[]>) {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = createApp(UserEmailPicker, { search })
  app.mount(host)
  return {
    host,
    unmount: () => {
      app.unmount()
      host.remove()
    },
  }
}

function buttonWithText(host: HTMLElement, text: string): HTMLButtonElement | undefined {
  return [...host.querySelectorAll('button')].find((button) =>
    button.textContent?.includes(text),
  ) as HTMLButtonElement | undefined
}

async function search(host: HTMLElement, email: string): Promise<void> {
  const input = host.querySelector('input') as HTMLInputElement
  input.value = email
  input.dispatchEvent(new Event('input', { bubbles: true }))
  await nextTick()
  buttonWithText(host, 'action.search')!.click()
  await new Promise((resolve) => setTimeout(resolve, 0))
  await nextTick()
}

describe('UserEmailPicker', () => {
  it('searches by full email and adds the selected user', async () => {
    const lookup = vi.fn(async () => [
      { id: 'u1', email: 'dev@example.com', nickname: 'Dev', avatar_url: null },
    ])
    const { host, unmount } = mountPicker(lookup)

    await search(host, 'dev@example.com')
    expect(lookup).toHaveBeenCalledWith('dev@example.com')
    expect(host.textContent).toContain('dev@example.com')

    buttonWithText(host, 'userEmailPicker.add')!.click()
    await nextTick()
    expect(host.textContent).toContain('userEmailPicker.selected')
    expect(host.textContent).toContain('Dev')

    unmount()
  })

  it('keeps disabled candidates (already a member) unselectable', async () => {
    const lookup = vi.fn(async () => [
      {
        id: 'u1',
        email: 'member@example.com',
        nickname: 'Member',
        avatar_url: null,
        disabled: true,
        note: 'already a member',
      },
    ])
    const { host, unmount } = mountPicker(lookup)

    await search(host, 'member@example.com')
    expect(buttonWithText(host, 'userEmailPicker.add')?.disabled).toBe(true)

    unmount()
  })
})