<script setup lang="ts">
import { useMediaQuery } from '@vueuse/core'
import { computed, watch } from 'vue'

import MenuCollapse from './components/MenuCollapse.vue'
import SideLogo from './components/SideLogo.vue'
import SideMenu from './components/SideMenu.vue'
import TheBreadcrumb from './components/TheBreadcrumb.vue'
import ThemeToggle from './components/ThemeToggle.vue'
import LanguageSwitcher from './components/LanguageSwitcher.vue'
import UserMenu from './components/UserMenu.vue'
import { COLLAPSE_BREAKPOINT, LAYOUT } from '@/settings/theme'
import { useAppStore } from '@/stores/app'
import { useUserStore } from '@/stores/user'

const appStore = useAppStore()
const userStore = useUserStore()

// 窄屏（平板 / 手机）强制收起侧栏，与参考模板断点行为一致
const isNarrowScreen = useMediaQuery(`(max-width: ${COLLAPSE_BREAKPOINT}px)`)
watch(
  isNarrowScreen,
  (narrow) => {
    appStore.setCollapsed(narrow)
  },
  { immediate: true },
)

/**
 * 缓存作用域 = 当前登录用户 id：KeepAlive 的实例 key。
 * 登录 / 登出切换 key 使旧用户缓存全部作废，避免跨账号脏数据。
 */
const cacheScope = computed(() => userStore.user?.id ?? 'anon')
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
      <header class="app-header" :style="{ height: `${LAYOUT.headerHeight}px` }">
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
        <!--
          面包屑链式缓存：meta.keepAlive 页面进 KeepAlive（:key=fullPath，参数页按 URL 区分实例），
          从评测结果 → 题目详情 → 列表逐级返回全程不刷新。:max=8 LRU 兜底——刚访问的链路页
          恒在缓存最前，超出后最久未用的实例自动释放。编辑向导等表单页不声明 keepAlive，进出重挂载。
          :key="cacheScope" 绑定登录用户，登出 / 换号后缓存整体作废。
        -->
        <router-view v-slot="{ Component, route }" :key="cacheScope">
          <keep-alive :max="8">
            <component
              :is="Component"
              v-if="route.meta.keepAlive"
              :key="route.fullPath"
            />
          </keep-alive>
          <component
            :is="Component"
            v-if="!route.meta.keepAlive"
            :key="route.fullPath"
          />
        </router-view>
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
