import type { RouteRecordRaw } from 'vue-router'

/**
 * 用户设置路由（hidden：不在前台侧栏显示；入口在头像菜单）。
 */
export const userRoutes: RouteRecordRaw[] = [
  {
    path: 'user',
    redirect: '/user/profile',
    meta: {
      title: '用户设置',
      titleKey: 'nav.userSettings',
      icon: 'Setting',
      hidden: true,
      requiresAuth: true,
    },
    children: [
      {
        path: 'profile',
        name: 'user-profile',
        component: () => import('@/views/user/ProfileView.vue'),
        meta: { title: '个人资料', titleKey: 'user.profile', icon: 'User', requiresAuth: true },
      },
      {
        path: 'security',
        name: 'user-security',
        component: () => import('@/views/user/SecurityView.vue'),
        meta: { title: '安全设置', titleKey: 'user.security', icon: 'Lock', requiresAuth: true },
      },
      {
        path: 'sessions',
        name: 'user-sessions',
        component: () => import('@/views/user/SessionsView.vue'),
        meta: {
          title: '会话管理',
          titleKey: 'user.sessions',
          icon: 'Odometer',
          requiresAuth: true,
          keepAlive: true,
        },
      },
    ],
  },
]
