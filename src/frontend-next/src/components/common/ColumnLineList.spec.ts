import { createApp, h } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import { i18n } from '@/i18n'
import ColumnLineList from './ColumnLineList.vue'

describe('ColumnLineList', () => {
  it('renders columns as borderless rows and forwards row clicks', async () => {
    const host = document.createElement('div')
    document.body.appendChild(host)
    const onRowClick = vi.fn()

    const app = createApp({
      render: () =>
        h(ColumnLineList, {
          columns: [{ key: 'name', title: 'Name' }],
          items: [{ name: 'Alpha' }],
          rowClick: onRowClick,
        }),
    })
    app.use(i18n)
    app.mount(host)

    expect(host.textContent).toContain('Name')
    expect(host.textContent).toContain('Alpha')

    const row = host.querySelector('[role="button"]')
    expect(row).not.toBeNull()
    row!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    expect(onRowClick).toHaveBeenCalledWith({ name: 'Alpha' })

    app.unmount()
    host.remove()
  })
})
