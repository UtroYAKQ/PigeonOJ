<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'

import MenuCollapse from './components/MenuCollapse.vue'
import SideLogo from './components/SideLogo.vue'
import SideMenu from './components/SideMenu.vue'
import TheBreadcrumb from './components/TheBreadcrumb.vue'
import ThemeToggle from './components/ThemeToggle.vue'
import LanguageSwitcher from './components/LanguageSwitcher.vue'
import UserMenu from './components/UserMenu.vue'
import { COLLAPSE_BREAKPOINT, LAYOUT } from '@/settings/theme'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

// 窄屏（平板 / 手机）强制收起侧栏，与参考模板断点行为一致
const media = window.matchMedia(`(max-width: ${COLLAPSE_BREAKPOINT}px)`)
function applyBreakpoint() {
  appStore.setCollapsed(media.matches)
}
onMounted(() => {
  applyBreakpoint()
  media.addEventListener('change', applyBreakpoint)
})
onBeforeUnmount(() => media.removeEventListener('change', applyBreakpoint))
</script>

<template>
  <n-layout class="app-layout" has-sider>
    <n-layout-sider
      bordered
      collapse-mode="width"
      :collapsed="appStore.collapsed"
      :collapsed-width="LAYOUT.siderCollapsedWidth"
      :width="LAYOUT.siderWidth"
      :native-scrollbar="false"
      class="app-sider"
    >
      <SideLogo />
      <SideMenu />
    </n-layout-sider>

    <article class="app-body">
      <header
        class="app-header"
        :style="{ height: `${LAYOUT.headerHeight}px` }"
      >
        <div class="app-header__left">
          <MenuCollapse />
          <TheBreadcrumb class="app-header__crumbs" />
        </div>
        <div class="app-header__actions">
          <LanguageSwitcher />
          <ThemeToggle />
          <UserMenu />
        </div>
      </header>

      <main class="app-main">
        <router-view />
      </main>
      <footer v-if="appStore.siteConfig.icp" class="app-footer">
        {{ appStore.siteConfig.icp }}
      </footer>
    </article>
  </n-layout>
</template>

<style scoped>
.app-layout {
  height: 100dvh;
}
.app-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}
.app-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 16px;
  background: var(--app-chrome-bg);
  border-bottom: 1px solid var(--app-border);
}
.app-header__left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.app-header__crumbs {
  /* 窄屏隐藏面包屑，参考模板同款行为 */
  display: none;
}
@media (min-width: 667px) {
  .app-header__crumbs {
    display: flex;
  }
}
.app-header__actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 6px;
}
/* 内容画布：浅灰蓝底 + 白卡片由各页面承载 */
.app-main {
  flex: 1;
  overflow: auto;
  padding: 14px;
  background: var(--app-content-bg);
}
/* ICP 备案号（系统配置 site.icp，非空才渲染） */
.app-footer {
  flex-shrink: 0;
  padding: 6px 16px;
  text-align: center;
  font-size: 12px;
  color: var(--app-text-secondary);
  background: var(--app-chrome-bg);
  border-top: 1px solid var(--app-border);
}
</style>
