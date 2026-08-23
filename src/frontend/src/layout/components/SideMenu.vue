<script setup lang="ts">
import { Back } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { layoutChildren } from '@/router'
import { useUserStore } from '@/stores/user'

import { resolveIcon } from '../icon'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

interface MenuItem { path: string; title: string; icon?: string }

/** 后台空间：/admin 下侧栏切换为管理菜单，与前台菜单互斥 */
const isAdminArea = computed(() => route.path.startsWith('/admin'))

const titleKeys: Record<string, string> = {
  home: 'nav.home', problems: 'nav.problems', contests: 'nav.contests', teams: 'nav.teams',
}
const mainMenus = computed<MenuItem[]>(() => layoutChildren
  .filter((r) => (r.meta?.titleKey || r.meta?.title) && !r.meta.hidden)
  .filter((r) => !r.meta?.roles || r.meta.roles.length === 0 || userStore.hasAnyRole(r.meta.roles))
  .map((r) => {
    const key = r.meta?.titleKey ?? titleKeys[String(r.name)]
    return { path: r.path === '' ? '/' : `/${r.path}`, title: key ? t(String(key)) : String(r.meta?.title ?? ''), icon: r.meta?.icon }
  }))

const adminSection = layoutChildren.find((r) => r.path === 'admin')
const adminMenus = computed<MenuItem[]>(() => (adminSection?.children ?? [])
  .filter((c) => c.meta?.titleKey && !c.meta.hidden && !c.meta.contextPage)
  .map((c) => ({
    path: `/admin/${c.path}`,
    title: t(String(c.meta?.titleKey)),
    icon: c.meta?.icon,
  })))

const menus = computed<MenuItem[]>(() => (isAdminArea.value ? adminMenus.value : mainMenus.value))

/**
 * 前台一级菜单代表区块根路由：子页（/problems/:id 等）仍需使区块项保持激活；
 * 后台空间内每项即具体页面，直接精确匹配。
 */
const activeMenuPath = computed(() => {
  if (isAdminArea.value) return route.path
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
    <!-- collapse 固定为 true：图标栏形态，悬浮由 EP 自带 tooltip 提示名称 -->
    <el-menu class="side-menu" :default-active="activeMenuPath" router collapse>
      <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
        <el-icon v-if="m.icon"><component :is="resolveIcon(m.icon)" /></el-icon>
        <template #title>{{ m.title }}</template>
      </el-menu-item>
    </el-menu>
  </el-scrollbar>
  <!-- 后台空间底部：返回前台 -->
  <div v-if="isAdminArea" class="side-footer">
    <el-tooltip :content="t('admin.backToApp')" placement="right">
      <button type="button" class="side-exit" @click="router.push('/')">
        <el-icon><Back /></el-icon>
      </button>
    </el-tooltip>
  </div>
</template>

<style scoped>
.side-menu-scroll{flex:1;overflow:hidden}.side-menu{border-right:0;background:transparent}.side-menu.el-menu--collapse{width:100%}.side-menu :deep(.el-menu-item){height:48px;margin:4px auto;border-radius:11px;color:var(--app-text-muted);font-weight:580;transition:background .18s,color .18s,transform .18s}.side-menu :deep(.el-menu-item .el-icon){font-size:19px}.side-menu :deep(.el-menu-item:hover){background:var(--app-surface-muted);color:var(--app-text);transform:none}.side-menu :deep(.el-menu-item.is-active){background:var(--el-color-primary-light-9);color:var(--el-color-primary);font-weight:720}

.side-footer{flex-shrink:0;padding:8px 6px;border-top:1px solid var(--app-border)}
.side-exit{width:100%;height:44px;display:grid;place-items:center;border:0;background:transparent;border-radius:11px;color:var(--app-text-muted);cursor:pointer;font-size:19px;transition:background .18s,color .18s}
.side-exit:hover{background:var(--app-surface-muted);color:var(--app-text)}
.side-exit:focus-visible{outline:none;box-shadow:0 0 0 3px var(--el-color-primary-light-7)}
</style>
