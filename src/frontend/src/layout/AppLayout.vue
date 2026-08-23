<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import LanguageSwitcher from './components/LanguageSwitcher.vue'
import SectionTabs from './components/SectionTabs.vue'
import SideMenu from './components/SideMenu.vue'
import UserMenu from './components/UserMenu.vue'

const route = useRoute(); const router = useRouter(); const { t } = useI18n()

interface Crumb { label: string; to?: string }

/**
 * 面包屑定位：只反映真实层级（如 管理后台/用户管理、题库/题目详情）；
 * 首页与顶级区块（题库/比赛/团队）互相平级，不作为面包屑起点。
 */
const breadcrumbs = computed<Crumb[]>(() => {
  const crumbs: Crumb[] = []
  route.matched.forEach((record, index) => {
    if (!record.meta?.titleKey && !record.meta?.title) return
    if (record.path === '') return // 根路由即首页，平级关系不入面包屑
    const label = record.meta?.titleKey ? t(String(record.meta.titleKey)) : String(record.meta?.title ?? '')
    if (!label || crumbs.some((c) => c.label === label)) return
    const isLast = index === route.matched.length - 1
    const target = !isLast && typeof record.redirect === 'string' ? record.redirect : undefined
    crumbs.push({ label, to: isLast ? undefined : (target ?? (record.path || '/')) })
  })
  if (crumbs.length === 1) crumbs[0].to = undefined // 仅剩单项时即为当前页，无需链接
  return crumbs
})
</script>
<template><el-container class="app-layout"><el-aside width="76px" class="app-aside"><div class="app-logo" role="button" tabindex="0" aria-label="PigeonOJ" @click="router.push('/')" @keyup.enter="router.push('/')"><span class="app-logo__mark">🐦</span></div><SideMenu/></el-aside><el-container class="app-body"><el-header class="app-header" height="68px"><el-breadcrumb v-if="breadcrumbs.length" separator="/" class="app-header__crumbs"><el-breadcrumb-item v-for="(c,i) in breadcrumbs" :key="`${i}-${c.label}`" :to="c.to">{{c.label}}</el-breadcrumb-item></el-breadcrumb><div class="app-header__actions"><LanguageSwitcher/><UserMenu/></div></el-header><SectionTabs/><el-main class="app-main"><div class="app-main__content"><router-view/></div></el-main></el-container></el-container></template>
<style scoped>
.app-layout{height:100dvh;background:var(--app-canvas)}.app-aside{display:flex;flex-direction:column;padding:12px 6px 10px;border-right:1px solid var(--app-border);background:var(--app-surface);overflow:hidden}.app-logo{height:52px;display:flex;align-items:center;justify-content:center;margin-bottom:8px;cursor:pointer;border-radius:12px;outline:none}.app-logo:focus-visible{box-shadow:0 0 0 3px var(--el-color-primary-light-7)}.app-logo__mark{width:40px;height:40px;display:grid;place-items:center;border-radius:12px;font-size:22px;background:linear-gradient(145deg,var(--el-color-primary-light-8),var(--el-color-primary-light-9))}.app-aside :deep(.side-menu-scroll){margin-top:4px}.app-header{height:68px;display:flex;align-items:center;justify-content:space-between;gap:16px;padding:0 28px;border-bottom:1px solid var(--app-border);background:color-mix(in srgb,var(--app-surface) 92%,transparent);backdrop-filter:blur(16px)}.app-header__crumbs{font-size:14px}.app-header__crumbs :deep(.el-breadcrumb__inner.is-link){font-weight:620;color:var(--app-text-muted)}.app-header__crumbs :deep(.el-breadcrumb__inner.is-link:hover){color:var(--el-color-primary)}.app-header__crumbs :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner){color:var(--app-text);font-weight:700}.app-header__actions{display:flex;align-items:center;gap:12px;margin-left:auto}.app-main{padding:28px;overflow:auto;background:var(--app-canvas)}.app-main__content{max-width:1440px;margin:0 auto}@media(max-width:767px){.app-header{padding:0 16px}.app-main{padding:16px}}
</style>
