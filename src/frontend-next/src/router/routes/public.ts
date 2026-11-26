import type { RouteRecordRaw } from 'vue-router'

/**
 * 独立布局路由（不经过 AppLayout；公开页面）。
 */
export const publicRoutes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { title: '登录', titleKey: 'user.login', public: true },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/auth/RegisterView.vue'),
    meta: { title: '注册', titleKey: 'user.register', public: true },
  },
  {
    path: '/verify/:token',
    name: 'verify-invite',
    component: () => import('@/views/problems/VerifyInviteView.vue'),
    meta: { title: '验题邀请', titleKey: 'problems.verify.title', public: true },
  },
]
