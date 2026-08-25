import { ref } from 'vue'

interface UsePaginationOptions {
  defaultPageSize?: number
}

/**
 * 分页状态 composable：共享 page / pageSize / total 与翻页逻辑。
 * 从 ProblemListView / ProblemMineView 等列表页提取。
 */
export function usePagination(options: UsePaginationOptions = {}) {
  const { defaultPageSize = 20 } = options
  const page = ref(1)
  const pageSize = ref(defaultPageSize)
  const total = ref(0)

  function changePage(value: number) {
    page.value = value
  }

  function changeSize(value: number) {
    pageSize.value = value
    page.value = 1
  }

  function resetPage() {
    page.value = 1
  }

  return { page, pageSize, total, changePage, changeSize, resetPage }
}
