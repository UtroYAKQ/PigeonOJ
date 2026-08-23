<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { resolveIcon } from '../icon'

const route = useRoute()
const { t } = useI18n()

/**
 * 右侧二级菜单栏：当前区块（matched[1]，即布局下的区块路由）有 ≥2 个带标题子项时渲染。
 * 例如「管理后台」区块（7 个子页）与「用户设置」区块（3 个子页）。
 */
const section = computed(() => route.matched[1])

const sectionTitle = computed(() => section.value?.meta?.titleKey ? t(String(section.value.meta.titleKey)) : '')

const tabs = computed(() => {
  const currentSection = section.value
  const children = currentSection?.children ?? []
  // route.children 的 path 是相对于区块路由的（如 `configs`），
  // Element Plus router 菜单需要绝对路径（`/admin/configs`）才能正确导航和激活。
  const basePath = currentSection?.path?.replace(/\/$/, '') ?? ''
  return children
    .filter((c) => c.meta?.titleKey && !c.meta?.hidden && !c.meta?.contextPage)
    .map((c) => ({
      path: c.path.startsWith('/') ? c.path : `${basePath}/${c.path}`,
      title: c.meta?.titleKey ? t(String(c.meta.titleKey)) : '',
      icon: c.meta?.icon,
    }))
})
</script>

<template>
  <div v-if="tabs.length > 1" class="section-tabs">
    <span v-if="sectionTitle" class="section-tabs__title">{{ sectionTitle }}</span>
    <el-menu
      mode="horizontal"
      class="section-tabs__menu"
      :default-active="route.path"
      :ellipsis="false"
      router
    >
      <el-menu-item v-for="t in tabs" :key="t.path" :index="t.path">
        <el-icon v-if="t.icon"><component :is="resolveIcon(t.icon)" /></el-icon>
        <span>{{ t.title }}</span>
      </el-menu-item>
    </el-menu>
  </div>
</template>

<style scoped>
.section-tabs{min-height:48px;display:flex;align-items:center;padding:0 28px;background:var(--app-surface);border-bottom:1px solid var(--app-border)}.section-tabs__title{font-size:11px;font-weight:750;color:var(--app-text-muted);letter-spacing:.04em;text-transform:uppercase;margin-right:16px;white-space:nowrap}.section-tabs__menu{border-bottom:0;flex:1;background:transparent}.section-tabs__menu :deep(.el-menu-item){height:48px;line-height:48px;padding:0 14px;font-size:13px;font-weight:600;color:var(--app-text-muted)}.section-tabs__menu :deep(.el-menu-item.is-active){color:var(--el-color-primary);font-weight:750}.section-tabs__menu :deep(.el-menu-item:hover){background:transparent;color:var(--app-text)}@media(max-width:767px){.section-tabs{padding:0 16px}.section-tabs__title{display:none}.section-tabs__menu :deep(.el-menu-item){padding:0 10px}}
</style>
