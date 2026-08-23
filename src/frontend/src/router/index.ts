import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import { useUserStore } from '@/stores/user'
import { i18n } from '@/i18n'

/**
 * 布局下的区块路由（侧边栏菜单数据源）。
 * 规则：
 * - meta.title 作为侧边栏 / 二级菜单项文案
 * - meta.hidden 从侧边栏隐藏（用户设置入口在底部用户卡）
 * - meta.roles 做权限过滤（管理后台仅 admin）
 * - 区块（有 children 的路由）子项 ≥ 2 时，右侧内容区顶部渲染二级菜单栏（SectionTabs）
 */
export const layoutChildren: RouteRecordRaw[] = [
  {
    path: '',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { title: '首页', titleKey: 'nav.home', icon: 'HomeFilled' },
  },
  {
    path: 'problems',
    redirect: '/problems/list',
    meta: { title: '题库', titleKey: 'nav.problems', icon: 'Collection', sectionTitle: '题库' },
    children: [
      {
        path: 'list',
        name: 'problems',
        component: () => import('@/views/problems/ProblemListView.vue'),
        meta: { title: '题库', titleKey: 'nav.problems', icon: 'Collection' },
      },
      {
        path: 'new',
        name: 'problem-create',
        component: () => import('@/views/problems/ProblemCreateView.vue'),
        meta: { title: '创建题目', titleKey: 'problems.create.title', requiresAuth: true, hidden: true, contextPage: true },
      },
      {
        path: ':id/edit',
        name: 'problem-edit',
        component: () => import('@/views/problems/ProblemCreateView.vue'),
        meta: { title: '编辑题目', titleKey: 'problems.create.editTitle', requiresAuth: true, hidden: true, contextPage: true },
      },
      {
        path: ':id',
        name: 'problem-detail',
        component: () => import('@/views/problems/ProblemDetailView.vue'),
        meta: { title: '题目详情', titleKey: 'problems.detail.title', requiresAuth: true, hidden: true, contextPage: true },
      },
      {
        path: ':problemId/submissions/:id',
        name: 'submission-detail',
        component: () => import('@/views/problems/SubmissionView.vue'),
        meta: { title: '评测结果', titleKey: 'problems.submission.title', requiresAuth: true, hidden: true, contextPage: true },
      },
    ],
  },
  {
    path: 'contests',
    name: 'contests',
    component: () => import('@/views/PlaceholderView.vue'),
    meta: {
      title: '比赛',
      titleKey: 'nav.contests',
      icon: 'Trophy',
      placeholder: {
        titleKey: 'nav.contests',
        descriptionKey: 'placeholder.contestsDescription',
        endpoints: ['GET /api/v1/contests', 'POST /api/v1/contests/{id}/register', 'GET /api/v1/contests/{id}/rankings'],
      },
    },
  },
  {
    path: 'teams',
    name: 'teams',
    component: () => import('@/views/PlaceholderView.vue'),
    meta: {
      title: '团队',
      titleKey: 'nav.teams',
      icon: 'UserFilled',
      placeholder: {
        titleKey: 'nav.teams',
        descriptionKey: 'placeholder.teamsDescription',
        endpoints: ['GET /api/v1/teams', 'POST /api/v1/teams', 'POST /api/v1/teams/{id}/invites'],
      },
    },
  },
  {
    path: 'user',
    redirect: '/user/profile',
    meta: { title: '用户设置', titleKey: 'nav.userSettings', icon: 'Setting', hidden: true, requiresAuth: true, sectionTitle: '用户设置' },
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
        meta: { title: '会话管理', titleKey: 'user.sessions', icon: 'Odometer', requiresAuth: true },
      },
    ],
  },
  {
    path: 'admin',
    redirect: '/admin/users',
    meta: { title: '管理后台', titleKey: 'nav.admin', icon: 'Monitor', roles: ['admin'], sectionTitle: '管理后台' },
    children: [
      {
        path: 'users',
        name: 'admin-users',
        component: () => import('@/views/admin/AdminUsersView.vue'),
        meta: { title: '用户管理', titleKey: 'nav.users', icon: 'User', roles: ['admin'] },
      },
      {
        path: 'configs',
        name: 'admin-configs',
        component: () => import('@/views/admin/AdminConfigsView.vue'),
        meta: { title: '系统配置', titleKey: 'nav.configs', icon: 'Setting', roles: ['admin'] },
      },
      {
        path: 'logs',
        name: 'admin-logs',
        component: () => import('@/views/admin/AdminLogsView.vue'),
        meta: { title: '日志', titleKey: 'nav.logs', icon: 'Document', roles: ['admin'] },
      },
      {
        path: 'sandbox',
        name: 'admin-sandbox',
        component: () => import('@/views/admin/AdminSandboxView.vue'),
        meta: { title: '沙箱状态', titleKey: 'nav.sandbox', icon: 'Odometer', roles: ['admin'] },
      },
      {
        path: 'reports',
        name: 'admin-reports',
        component: () => import('@/views/admin/AdminReportsView.vue'),
        meta: { title: '举报管理', titleKey: 'nav.reports', icon: 'Warning', roles: ['admin'] },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      component: () => import('@/layout/AppLayout.vue'),
      children: layoutChildren,
    },
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
    // 未匹配路由：回首页
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

// 路由守卫：会话恢复 + 登录校验 + 角色校验（docs/architecture.md 权限设计）
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

function setDocumentTitle(meta: { titleKey?: string; title?: string }) {
  const translate = (i18n as unknown as { global: { t: (key: string) => string } }).global.t
  const title = meta.titleKey ? translate(String(meta.titleKey)) : meta.title
  document.title = title ? `${title} · PigeonOJ` : 'PigeonOJ'
}

router.afterEach((to) => setDocumentTitle(to.meta))
window.addEventListener('pigeonoj:locale-change', () => setDocumentTitle(router.currentRoute.value.meta))

export default router
