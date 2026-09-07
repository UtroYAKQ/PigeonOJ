import { describe, expect, it, vi, beforeEach } from 'vitest'
import { createApp, defineComponent, h, nextTick } from 'vue'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import naive from 'naive-ui'

import ProblemSetDetailView from '@/views/problemsets/ProblemSetDetailView.vue'
import type { ProblemSetDetail } from '@/types'

// jsdom 缺 naive-ui（vueuc）依赖的浏览器 API，补最小桩
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
;(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver ??= ResizeObserverStub
;(globalThis as unknown as { matchMedia: unknown }).matchMedia ??= () => ({
  matches: false,
  addListener: () => {},
  removeListener: () => {},
  addEventListener: () => {},
  removeEventListener: () => {},
  dispatchEvent: () => false,
})

async function flush() {
  for (let i = 0; i < 8; i++) {
    await Promise.resolve()
    await new Promise((r) => setTimeout(r, 0))
  }
  await nextTick()
}

const teamSetDetail: ProblemSetDetail = {
  id: '00000000-0000-0000-0000-00000000abcd',
  title: '团队题单A',
  visibility: 'team',
  status: 'active',
  owner_id: '00000000-0000-0000-0000-000000000001',
  item_count: 2,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  items: [
    {
      problem_id: '00000000-0000-0000-0000-00000000p001',
      title: '题目一',
      sort_order: 0,
      solved: null,
    },
    {
      problem_id: '00000000-0000-0000-0000-00000000p002',
      title: '题目二',
      sort_order: 1,
      solved: null,
    },
  ],
  can_manage: true,
  owner_name: 'tutor',
}

vi.mock('@/api/problemSets', () => ({
  getProblemSet: vi.fn(async () => teamSetDetail),
}))
vi.mock('@/api/teams', () => ({
  getTeamProblemSet: vi.fn(async () => teamSetDetail),
}))
vi.mock('@/utils/feedback', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
  dialog: { warning: vi.fn() },
  confirmAsyncDialog: vi.fn(),
}))

vi.mock('@/i18n', () => ({
  i18n: { global: { t: (key: string) => key } },
}))
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}))

async function mountView(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/teams/:teamId/sets/:setId',
        component: ProblemSetDetailView,
        meta: { keepAlive: false },
      },
    ],
  })
  await router.push(path)
  await router.isReady()

  const root = document.createElement('div')
  document.body.appendChild(root)
  const app = createApp(defineComponent({ render: () => h(RouterView) }))
  app.use(router)
  app.use(naive)
  app.mount(root)
  await flush()
  return root
}

describe('ProblemSetDetailView（团队题单详情）', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
  })

  it('items 非空：表格渲染行、空态隐藏（两者互斥）', async () => {
    const root = await mountView('/teams/t000/sets/s000')
    // 首屏渲染在「信息」tab；切到题目列表 tab 验证互斥渲染
    const tabs = [...root.querySelectorAll('.n-tabs-tab')]
    // t() 桩返回 key 本身，tab 文本含 key 的最后一段
    const problemsTab = tabs.find((el) => el.textContent?.includes('problems'))
    expect(problemsTab).not.toBeNull()
    ;(problemsTab as HTMLElement).dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flush()

    const emptyEls = [...root.querySelectorAll('.problems-empty')]
    for (const el of emptyEls) {
      expect((el as HTMLElement).style.display).toBe('none')
    }
    const tableEl = root.querySelector('.n-data-table')
    expect(tableEl).not.toBeNull()
    const rows = root.querySelectorAll('.n-data-table .n-data-table-tr')
    expect(rows.length).toBeGreaterThanOrEqual(2)
  })
})
