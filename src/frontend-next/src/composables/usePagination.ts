import { ref } from 'vue'

interface UsePaginationOptions {
  defaultPageSize?: number
}

/**
 * 分页状态 composable：共享 page / pageSize / total 与翻页逻辑。
 * 从 ProblemListView / ProblemMineView 等列表页提取。
 *
 * 竞态守卫：分页请求慢返回会覆盖新数据（如先点末页再点首页，末页响应后到把
 * 第一页数据刷掉，且页码已停在第 1 页导致再点无效）。每次发起加载先取序号
 * beginLoad()，响应处理前用 isCurrent(seq) 判断是否已被更新的请求取代。
 */
export function usePagination(options: UsePaginationOptions = {}) {
  const { defaultPageSize = 20 } = options
  const page = ref(1)
  const pageSize = ref(defaultPageSize)
  const total = ref(0)

  let requestSeq = 0
  /** 发起一次加载前调用：返回本次加载序号 */
  function beginLoad(): number {
    return ++requestSeq
  }
  /** 响应处理前调用：false = 该响应已过期，应丢弃（不写状态、不清 loading） */
  function isCurrent(seq: number): boolean {
    return seq === requestSeq
  }

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

  return { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent }
}
