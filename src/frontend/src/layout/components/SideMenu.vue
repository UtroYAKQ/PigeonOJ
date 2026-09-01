<script setup lang="ts">
import { computed, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NIcon } from 'naive-ui'
import { Back } from '@element-plus/icons-vue'

import { layoutChildren } from '@/router'
import { useUserStore } from '@/stores/user'
import { useAppStore } from '@/stores/app'

import { resolveIcon } from '../icon'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()
const appStore = useAppStore()

interface MenuItem {
  path: string
  titleKey?: string
  title?: string
  icon?: string
}

interface MenuOption {
  label: string
  key: string
  icon?: () => ReturnType<typeof h>
}

/** 后台空间：/admin 下侧栏切换为管理菜单，与前台菜单互斥 */
const isAdminArea = computed(() => route.path.startsWith('/admin'))

/**
 * 前台一级菜单：单可见子路由的区块（如 题库→列表）拍平为单项；
 * hidden（用户设置 / 管理后台入口在头像菜单）与未授权区块不出现。
 */
const frontMenus = computed<MenuItem[]>(() =>
  layoutChildren
    .filter((r) => !r.meta?.hidden && (r.meta?.titleKey || r.meta?.title))
    .filter(
      (r) =>
        !r.meta?.roles ||
        r.meta.roles.length === 0 ||
        userStore.hasAnyRole(r.meta.roles as string[]),
    )
    .map((r) => {
      const visibleChildren = (r.children ?? []).filter(
        (c) => !c.meta?.hidden && (c.meta?.titleKey || c.meta?.title),
      )
      if (r.children?.length && visibleChildren.length === 1) {
        const child = visibleChildren[0]
        return {
          path: `/${[r.path, child.path].filter((p) => p && p !== '/').join('/')}`,
          titleKey: (child.meta?.titleKey as string | undefined) ?? r.meta?.titleKey,
          title: (child.meta?.title as string | undefined) ?? r.meta?.title,
          icon: (child.meta?.icon as string | undefined) ?? r.meta?.icon,
        }
      }
      return {
        path: r.path === '' ? '/' : `/${r.path}`,
        titleKey: r.meta?.titleKey,
        title: r.meta?.title,
        icon: r.meta?.icon,
      }
    }),
)

/** 后台空间菜单：管理后台各子页（按角色过滤，tutor 仅见题目管理） */
const adminMenus = computed<MenuItem[]>(() => {
  const adminSection = layoutChildren.find((r) => r.path === 'admin')
  return (adminSection?.children ?? [])
    .filter((c) => c.meta?.titleKey && !c.meta?.hidden && !c.meta?.contextPage)
    .filter(
      (c) =>
        !c.meta?.roles ||
        c.meta.roles.length === 0 ||
        userStore.hasAnyRole(c.meta.roles as string[]),
    )
    .map((c) => ({
      path: `/admin/${c.path}`,
      titleKey: c.meta?.titleKey,
      title: c.meta?.title,
      icon: c.meta?.icon,
    }))
})

const menus = computed(() => (isAdminArea.value ? adminMenus.value : frontMenus.value))

function menuIcon(name?: string) {
  const comp = resolveIcon(name)
  if (!comp) return undefined
  return () => h(NIcon, null, { default: () => h(comp) })
}

const menuOptions = computed<MenuOption[]>(() =>
  menus.value.map((m) => ({
    label: m.titleKey ? t(m.titleKey) : (m.title ?? ''),
    key: m.path,
    icon: menuIcon(m.icon),
  })),
)

/**
 * 激活定位：先取当前所属区块根（route.matched[1]，如 /problems），
 * 再映射到可见菜单中该区块的菜单项（拍平后的题库项为 /problems/list）。
 * 区块内任意子页（详情 / 新建 / 提交结果）都保持同一菜单项高亮；首页精确匹配自身。
 */
const activePath = computed(() => {
  if (isAdminArea.value) {
    // 后台上下文页（如 /admin/problems/new）归属其区块菜单项
    const segments = route.path.split('/')
    return segments.length > 3 ? segments.slice(0, 3).join('/') : route.path
  }
  const sectionPath = (route.matched[1]?.path ?? '').replace(/\/$/, '')
  if (!sectionPath) return route.path
  const hit = frontMenus.value.find(
    (item) => item.path === sectionPath || item.path.startsWith(`${sectionPath}/`),
  )
  return hit?.path ?? route.path
})

function onSelect(key: string) {
  router.push(key)
}
</script>

<template>
  <div class="side-menu-wrap">
    <!-- 折叠态由父级 n-layout-sider 驱动；收起时 Naive 自动以 tooltip 显示名称 -->
    <n-menu
      class="side-menu"
      accordion
      :indent="18"
      :collapsed="appStore.collapsed"
      :collapsed-width="64"
      :collapsed-icon-size="20"
      :options="menuOptions"
      :value="activePath"
      @update:value="onSelect"
    />
    <!-- 后台空间底部：返回前台 -->
    <div v-if="isAdminArea" class="side-footer" :class="{ collapsed: appStore.collapsed }">
      <n-tooltip trigger="hover" placement="right">
        <template #trigger>
          <button
            type="button"
            class="side-exit"
            :aria-label="t('admin.backToApp')"
            @click="router.push('/')"
          >
            <n-icon :component="Back" />
          </button>
        </template>
        {{ t('admin.backToApp') }}
      </n-tooltip>
    </div>
  </div>
</template>

<style scoped>
.side-menu-wrap {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.side-menu {
  flex: 1;
}
/* 参考模板同款选中/悬停样式：左侧 4px 主色描边 */
.side-menu :deep(.n-menu-item-content::before) {
  left: 5px;
  right: 5px;
}
.side-menu :deep(.n-menu-item-content--selected::before),
.side-menu :deep(.n-menu-item-content:hover::before) {
  border-left: 4px solid var(--app-primary);
}
.side-footer {
  flex-shrink: 0;
  padding: 8px 10px;
  border-top: 1px solid var(--app-border);
}
.side-footer.collapsed {
  padding: 8px 6px;
}
.side-exit {
  width: 100%;
  height: 36px;
  display: grid;
  place-items: center;
  border: 0;
  background: transparent;
  border-radius: 3px;
  color: var(--app-text-secondary);
  cursor: pointer;
  font-size: 17px;
  transition:
    background-color 0.15s ease,
    color 0.15s ease;
}
.side-exit:hover {
  background: var(--app-muted-bg);
  color: var(--app-primary);
}
.side-exit:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--app-primary);
}
</style>
