import { ref, shallowRef } from 'vue'
import { useI18n } from 'vue-i18n'

import { usePagination } from '@/composables/usePagination'
import { message } from '@/utils/feedback'
import type { PageResult } from '@/types'

export interface TeamModuleQuery {
  page: number
  page_size: number
  keyword?: string
}

/**
 * 团队详情模块列表的通用加载器：分页 + 关键词 + 请求竞态守卫。
 * 各模块 tab 懒加载后常驻，切换 tab 不重复请求。
 */
export function useTeamModuleList<T>(loader: (query: TeamModuleQuery) => Promise<PageResult<T>>) {
  const { t } = useI18n()
  const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
    usePagination({ defaultPageSize: 10 })

  const loading = ref(false)
  const rows = shallowRef<T[]>([])
  const keyword = ref('')

  async function load(): Promise<void> {
    const seq = beginLoad()
    loading.value = true
    try {
      const result = await loader({
        page: page.value,
        page_size: pageSize.value,
        keyword: keyword.value || undefined,
      })
      if (!isCurrent(seq)) return
      rows.value = result.items
      total.value = result.total
    } catch (error) {
      if (!isCurrent(seq)) return
      message.error(error instanceof Error ? error.message : t('common.loadFailed'))
    } finally {
      if (isCurrent(seq)) loading.value = false
    }
  }

  function onSearch(): void {
    resetPage()
    void load()
  }

  function onPage(value: number): void {
    changePage(value)
    void load()
  }

  function onPageSize(value: number): void {
    changeSize(value)
    void load()
  }

  return {
    loading,
    rows,
    keyword,
    page,
    pageSize,
    total,
    load,
    onSearch,
    onPage,
    onPageSize,
  }
}
