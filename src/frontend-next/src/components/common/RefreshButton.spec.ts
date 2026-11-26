import { createApp, h } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import { TooltipProvider } from '@/components/ui/tooltip'
import { i18n } from '@/i18n'
import RefreshButton from './RefreshButton.vue'

describe('RefreshButton', () => {
  it('forwards click to the consumer so lists can reload', async () => {
    const onClick = vi.fn()
    const host = document.createElement('div')
    document.body.appendChild(host)

    const app = createApp({
      render: () =>
        h(TooltipProvider, null, {
          default: () => h(RefreshButton, { label: 'Refresh', onClick }),
        }),
    })
    app.use(i18n)
    app.mount(host)

    const button = host.querySelector('button')
    expect(button).not.toBeNull()
    button!.click()
    expect(onClick).toHaveBeenCalledTimes(1)

    app.unmount()
    host.remove()
  })
})
