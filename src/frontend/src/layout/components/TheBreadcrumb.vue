<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

interface Crumb {
  label: string
  to?: string
}

/**
 * 面包屑定位：只反映真实层级（如 管理后台/用户管理、题库/题目详情）；
 * 首页与顶级区块互相平级，不作为面包屑起点。
 */
const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const crumbs = computed<Crumb[]>(() => {
  const items: Crumb[] = []
  route.matched.forEach((record, index) => {
    if (!record.meta?.titleKey && !record.meta?.title) return
    if (record.path === '') return // 根路由即首页，平级关系不入面包屑
    const label = record.meta?.titleKey
      ? t(String(record.meta.titleKey))
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
      const parentLabel = t(String(parent.titleKey))
      if (items.some((c) => c.label === parentLabel)) continue
      const parentPath = typeof parent.path === 'function' ? parent.path(route) : parent.path
      items.splice(Math.max(items.length - 1, 0), 0, { label: parentLabel, to: parentPath })
    }
  }

  if (items.length === 1) items[0].to = undefined // 仅剩单项时即为当前页，无需链接
  return items
})
</script>

<template>
  <nav v-if="crumbs.length" class="breadcrumb" aria-label="Breadcrumb">
    <template v-for="(c, i) in crumbs" :key="`${i}-${c.label}`">
      <span v-if="i > 0" class="breadcrumb__sep">/</span>
      <component
        :is="c.to ? 'button' : 'span'"
        class="breadcrumb__item"
        :class="{ link: !!c.to, current: !c.to }"
        @click="c.to && router.push(c.to)"
        >{{ c.label }}</component
      >
    </template>
  </nav>
</template>

<style scoped>
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font-size: 14px;
}
.breadcrumb__sep {
  color: var(--app-text-secondary);
}
.breadcrumb__item {
  padding: 0;
  border: 0;
  background: transparent;
  font: inherit;
  white-space: nowrap;
}
.breadcrumb__item.link {
  color: var(--app-text-secondary);
  cursor: pointer;
}
.breadcrumb__item.link:hover {
  color: var(--app-primary);
}
.breadcrumb__item.current {
  color: var(--app-text);
  font-weight: 600;
}
</style>
