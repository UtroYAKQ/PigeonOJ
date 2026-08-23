<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { layoutChildren } from '@/router'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'

import { resolveIcon } from '../icon'

const route = useRoute()
const { t } = useI18n()
const appStore = useAppStore()
const userStore = useUserStore()

interface MenuItem { path: string; title: string; icon?: string }
const titleKeys: Record<string, string> = {
  home: 'nav.home', problems: 'nav.problems', contests: 'nav.contests', teams: 'nav.teams', admin: 'nav.admin',
}
const menus = computed<MenuItem[]>(() => layoutChildren
  .filter((r) => (r.meta?.titleKey || r.meta?.title) && !r.meta.hidden)
  .filter((r) => !r.meta?.roles || r.meta.roles.length === 0 || userStore.hasAnyRole(r.meta.roles))
  .map((r) => {
    const key = r.meta?.titleKey ?? titleKeys[String(r.name)]
    return { path: r.path === '' ? '/' : `/${r.path}`, title: key ? t(String(key)) : String(r.meta?.title ?? ''), icon: r.meta?.icon }
  }))

/**
 * 一级菜单只代表区块根路由。子页（/admin/configs 等）仍需使 /admin 保持激活，
 * 否则 Element Plus 的精确 path 匹配会取消「管理后台」高亮。
 */
const activeMenuPath = computed(() => {
  const matchedSection = route.matched[1]
  if (matchedSection?.path) {
    const sectionPath = matchedSection.path.replace(/\/$/, '')
    return sectionPath || '/'
  }
  return route.path
})
</script>

<template>
  <el-scrollbar class="side-menu-scroll">
    <p v-show="!appStore.sidebarCollapsed" class="side-menu__label">{{ t('app.navigation') }}</p>
    <el-menu class="side-menu" :default-active="activeMenuPath" :collapse="appStore.sidebarCollapsed" :collapse-transition="false" router>
      <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
        <el-icon v-if="m.icon"><component :is="resolveIcon(m.icon)" /></el-icon>
        <template #title>{{ m.title }}</template>
      </el-menu-item>
    </el-menu>
  </el-scrollbar>
</template>

<style scoped>
.side-menu-scroll{flex:1;overflow:hidden}.side-menu__label{margin:8px 12px 9px;color:var(--app-text-muted);font-size:10px;font-weight:750;letter-spacing:.11em}.side-menu{border-right:0;background:transparent}.side-menu :deep(.el-menu-item){height:48px;margin:4px 0;border-radius:11px;color:var(--app-text-muted);font-weight:580;transition:background .18s,color .18s,transform .18s}.side-menu :deep(.el-menu-item .el-icon){font-size:18px}.side-menu :deep(.el-menu-item:hover){background:var(--app-surface-muted);color:var(--app-text);transform:translateX(2px)}.side-menu :deep(.el-menu-item.is-active){background:var(--el-color-primary-light-9);color:var(--el-color-primary);font-weight:720}.side-menu :deep(.el-menu--collapse .el-menu-item){padding:0 19px}.side-menu :deep(.el-menu--collapse .el-menu-item:hover){transform:none}
</style>
