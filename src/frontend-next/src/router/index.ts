import { createRouter, createWebHistory } from 'vue-router'

import { frontRoutes } from './routes/front'
import { adminRoutes } from './routes/admin'
import { userRoutes } from './routes/user'
import { publicRoutes } from './routes/public'
import { registerGuards, setDocumentTitle } from './guards'

/**
 * 布局下的区块路由（侧边栏菜单数据源）。
 * SideMenu.vue 依赖此导出渲染菜单 + 激活定位。
 */
export const layoutChildren = [...frontRoutes, ...adminRoutes, ...userRoutes]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    {
      path: '/',
      component: () => import('@/layout/AppLayout.vue'),
      children: layoutChildren,
    },
    ...publicRoutes,
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

registerGuards(router)

/** 站点配置异步加载完成后刷新标签标题（App.vue watch 调用）。 */
export function refreshDocumentTitle() {
  setDocumentTitle(router.currentRoute.value.meta)
}

export default router
