import type { Router } from 'vue-router'

import { useUserStore } from '@/stores/user'
import { useAppStore } from '@/stores/app'
import { i18n } from '@/i18n'

export function setDocumentTitle(meta: { titleKey?: string; title?: string }) {
  const translate = (i18n as unknown as { global: { t: (key: string) => string } }).global.t
  const title = meta.titleKey ? translate(String(meta.titleKey)) : meta.title
  const siteName = useAppStore().siteName
  document.title = title ? `${title} · ${siteName}` : siteName
}

/** 注册路由守卫：会话恢复 + 登录校验 + 角色校验 + 动态标题。 */
export function registerGuards(router: Router) {
  router.beforeEach(async (to) => {
    const userStore = useUserStore()
    if (!userStore.initialized) {
      await userStore.init()
    }
    if (to.meta.public) return true
    if (to.meta.requiresAuth && !userStore.isLoggedIn) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
    if (to.meta.roles && to.meta.roles.length > 0 && !userStore.hasAnyRole(to.meta.roles)) {
      return { path: '/', query: { denied: '1' } }
    }
    return true
  })

  router.afterEach((to) => setDocumentTitle(to.meta))
  // 语言切换 / 站点配置加载完成都可能改变标题组成部分，均重设 tab 标题
  window.addEventListener('pigeonoj:locale-change', () =>
    setDocumentTitle(router.currentRoute.value.meta),
  )
  window.addEventListener('pigeonoj:site-config-change', () =>
    setDocumentTitle(router.currentRoute.value.meta),
  )
}
