import type { RouteLocationNormalizedLoaded } from 'vue-router'

export interface CrumbItem {
  label: string
  to?: string
}

/**
 * 面包屑构建：只反映真实层级（如 管理后台/用户管理、题库/题目详情）；
 * 首页与顶级区块互相平级，不作为面包屑起点。
 * TheBreadcrumb（展示）与 AppLayout（面包屑链式缓存）共用，保证两处层级解析永远一致。
 */
export function buildCrumbs(
  route: RouteLocationNormalizedLoaded,
  translate: (key: string) => string,
): CrumbItem[] {
  const items: CrumbItem[] = []
  route.matched.forEach((record, index) => {
    if (!record.meta?.titleKey && !record.meta?.title) return
    if (record.path === '') return // 根路由即首页，平级关系不入面包屑
    const label = record.meta?.titleKey
      ? translate(String(record.meta.titleKey))
      : String(record.meta?.title ?? '')
    if (!label || items.some((c) => c.label === label)) return
    const isLast = index === route.matched.length - 1
    const target = !isLast && typeof record.redirect === 'string' ? record.redirect : undefined
    items.push({ label, to: isLast ? undefined : (target ?? (record.path || '/')) })
  })

  // 上下文页归属工作台：在末项前插入面包屑父级（如 题库/题目管理/编辑题目；
  // 题单上下文写题页挂到具体题单详情 —— path 支持按当前路由参数解析动态路径；
  // 数组形式声明多级父链，按序插入：题单/题单详情/题目详情/评测结果）
  const leafMeta = route.matched[route.matched.length - 1]?.meta
  const parentConfig = leafMeta?.breadcrumbParent
  const parents = parentConfig ? (Array.isArray(parentConfig) ? parentConfig : [parentConfig]) : []
  if (parents.length && items.length >= 1) {
    for (const parent of parents) {
      const parentLabel = translate(String(parent.titleKey))
      if (items.some((c) => c.label === parentLabel)) continue
      const parentPath = typeof parent.path === 'function' ? parent.path(route) : parent.path
      items.splice(Math.max(items.length - 1, 0), 0, { label: parentLabel, to: parentPath })
    }
  }

  if (items.length === 1) items[0].to = undefined // 仅剩单项时即为当前页，无需链接
  return items
}

