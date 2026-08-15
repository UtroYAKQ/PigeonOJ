import { createRouter, createWebHistory } from 'vue-router'

// 骨架阶段仅占位首页；业务页面按 docs/contracts/ 各模块契约逐步加入
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
    },
  ],
})

export default router
