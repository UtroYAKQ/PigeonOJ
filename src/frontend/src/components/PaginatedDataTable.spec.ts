import { describe, expect, it } from 'vitest'
import { createApp, defineComponent, h, nextTick, ref } from 'vue'
import naive from 'naive-ui'

import PaginatedDataTable from './PaginatedDataTable.vue'
import { usePagination } from '@/composables/usePagination'

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

/** 等待微任务 + 宏任务多轮排空（加载链路跨多层异步） */
async function flush() {
  for (let i = 0; i < 8; i++) {
    await Promise.resolve()
    await new Promise((r) => setTimeout(r, 0))
  }
  await nextTick()
}

/** 按页码文本点击真实分页项（naive 渲染为 li.n-pagination-item，onClick 绑定在 li 上） */
function clickPageItem(root: HTMLElement, page: number) {
  const item = [...root.querySelectorAll('.n-pagination-item')].find(
    (el) => el.textContent?.trim() === String(page),
  )
  if (!item) throw new Error(`分页项 ${page} 不存在`)
  item.dispatchEvent(new MouseEvent('click', { bubbles: true }))
}

function activePage(root: HTMLElement): string | undefined {
  return root.querySelector('.n-pagination-item--active')?.textContent?.trim()
}

/**
 * 完整复刻日志等列表页的接线和 load() 模式（usePagination 序号守卫 + v-model:page），
 * 数据加载用手动 resolve 的受控 Promise，可模拟「慢响应后到」。
 */
function mountHarness() {
  type Pending = { page: number; resolve: (r: { items: string[]; total: number }) => void }
  const pending: Pending[] = []
  const requested: number[] = []
  const rows = ref<string[]>([])
  const loading = ref(false)

  const Harness = defineComponent({
    setup() {
      const { page, pageSize, total, changePage, changeSize, beginLoad, isCurrent } =
        usePagination()
      async function load() {
        const seq = beginLoad()
        requested.push(page.value)
        loading.value = true
        try {
          const result = await new Promise<{ items: string[]; total: number }>((resolve) => {
            pending.push({ page: page.value, resolve })
          })
          if (!isCurrent(seq)) return
          rows.value = result.items
          total.value = result.total
        } finally {
          if (isCurrent(seq)) loading.value = false
        }
      }
      // 复刻列表页 onMounted(load)：首屏加载产生 total 与页码项
      load()
      return () =>
        h(PaginatedDataTable, {
          columns: [],
          data: rows.value,
          loading: loading.value,
          total: total.value,
          page: page.value,
          pageSize: pageSize.value,
          pageSizes: [10, 20, 50],
          tableProps: { remote: true },
          // 真实页面 v-model:page + @update:page 合并为同一监听器数组：先同步 page，再触发加载
          'onUpdate:page': (v: number) => {
            page.value = v
            changePage(v)
            load()
          },
          'onUpdate:pageSize': (v: number) => {
            pageSize.value = v
            changeSize(v)
            load()
          },
        })
    },
  })

  const root = document.createElement('div')
  document.body.appendChild(root)
  createApp(Harness).use(naive).mount(root)

  return {
    root,
    requested,
    rows,
    loading,
    /** 取回指定页码的全部在途请求并放行 */
    resolvePage(page: number, items: string[], total = 170) {
      for (const p of pending.splice(0)) {
        if (p.page === page) p.resolve({ items, total })
        else pending.push(p)
      }
    },
  }
}

describe('PaginatedDataTable 分页交互（真实 naive-ui 渲染）', () => {
  it('点击末页(9)再点击第一页：页码与数据都回到第一页', async () => {
    const t = mountHarness()
    t.resolvePage(1, ['p1-1'], 170)
    await flush()
    expect(activePage(t.root)).toBe('1')
    expect(t.rows.value).toEqual(['p1-1'])

    clickPageItem(t.root, 9)
    t.resolvePage(9, ['p9-1'], 170)
    await flush()
    expect(activePage(t.root)).toBe('9')
    expect(t.rows.value).toEqual(['p9-1'])

    clickPageItem(t.root, 1)
    t.resolvePage(1, ['p1-2'], 170)
    await flush()
    expect(activePage(t.root)).toBe('1')
    expect(t.rows.value).toEqual(['p1-2'])
  })

  it('慢响应后到不覆盖新数据：点末页9（慢）→ 点首页（快），最终停留在首页', async () => {
    const t = mountHarness()
    t.resolvePage(1, ['p1-1'], 170)
    await flush()

    clickPageItem(t.root, 9) // 慢请求在途（未 resolve）
    await flush()
    expect(t.loading.value).toBe(true)

    clickPageItem(t.root, 1) // 加载中点击依然生效（分页器不禁用）
    t.resolvePage(1, ['p1-fast'], 170) // 首页快响应先回
    await flush()
    expect(activePage(t.root)).toBe('1')
    expect(t.rows.value).toEqual(['p1-fast'])

    t.resolvePage(9, ['p9-slow'], 170) // 末页慢响应后到 → 应被序号守卫丢弃
    await flush()
    expect(t.rows.value).toEqual(['p1-fast'])
    expect(activePage(t.root)).toBe('1')
  })

  it('加载中重复点击：最新一次点击胜出，过期响应全部丢弃', async () => {
    const t = mountHarness()
    t.resolvePage(1, ['p1-init'], 170)
    await flush()
    expect(t.rows.value).toEqual(['p1-init'])

    // 点击间 flush：模拟真实用户的点击节奏（DOM 随页码重渲染后再点下一个）
    clickPageItem(t.root, 9)
    await flush()
    clickPageItem(t.root, 3)
    await flush()
    clickPageItem(t.root, 1)
    await flush()
    t.resolvePage(9, ['p9'], 170) // 过期 → 丢弃
    t.resolvePage(3, ['p3'], 170) // 过期 → 丢弃
    await flush()
    expect(t.rows.value).toEqual(['p1-init']) // 仍是最初数据

    t.resolvePage(1, ['p1-latest'], 170) // 最新请求
    await flush()
    expect(t.rows.value).toEqual(['p1-latest'])
    expect(activePage(t.root)).toBe('1')
    expect(t.requested).toEqual([1, 9, 3, 1])
  })
})
