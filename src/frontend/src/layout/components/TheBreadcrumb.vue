<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { buildCrumbs } from '@/router/crumbs'

/**
 * 面包屑展示：层级解析收敛到 router/crumbs.ts（与 AppLayout 链式缓存共用同一解析，
 * 保证「点面包屑返回的页」与「被缓存的页」永远一致）。
 */
const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const crumbs = computed(() => buildCrumbs(route, (key) => t(key)))
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
