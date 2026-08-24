import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import { useUserStore } from '@/stores/user'
import { useAppStore } from '@/stores/app'
import { i18n } from '@/i18n'

/**
 * 布局下的区块路由（侧边栏菜单数据源）。
 * 规则：
 * - meta.titleKey 作为侧边栏 / 浏览器标题文案
 * - meta.hidden 从侧边栏隐藏（用户设置与管理后台由头像菜单进入）
 * - meta.roles 做权限过滤（管理后台仅 admin）
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
    meta: { title: '题库', titleKey: 'nav.problems', icon: 'Collection' },
    children: [
      {
        path: 'list',
        name: 'problems',
        component: () => import('@/views/problems/ProblemListView.vue'),
        meta: { title: '题库', titleKey: 'nav.problems', icon: 'Collection' },
      },
      {
        // 前台仅消费：详情 / 提交结果；出题入口统一在管理后台
        path: ':id',
        name: 'problem-detail',
        component: () => import('@/views/problems/ProblemDetailView.vue'),
        meta: {
          title: '题目详情',
          titleKey: 'problems.detail.title',
          requiresAuth: true,
          hidden: true,
          contextPage: true,
        },
      },
      {
        path: ':problemId/submissions/:id',
        name: 'submission-detail',
        component: () => import('@/views/problems/SubmissionView.vue'),
        meta: {
          title: '评测结果',
          titleKey: 'problems.submission.title',
          requiresAuth: true,
          hidden: true,
          contextPage: true,
        },
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
        endpoints: [
          'GET /api/v1/contests',
          'POST /api/v1/contests/{id}/register',
          'GET /api/v1/contests/{id}/rankings',
        ],
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
    path: 'admin',
    // staff 会话即可进入；tutor 落地题目管理，admin 落地用户管理
    redirect: () => {
      const userStore = useUserStore()
      return userStore.hasAnyRole(['admin']) ? '/admin/users' : '/admin/problems'
    },
    // hidden：不在前台侧栏显示；入口在头像菜单，进入后侧栏整体切换为管理菜单
    meta: {
      title: '管理后台',
      titleKey: 'nav.admin',
      icon: 'Monitor',
      roles: ['admin', 'tutor'],
      hidden: true,
    },
    children: [
      {
        // 出题工作台（管理后台唯一面向 tutor 的区块）；上下文页挂其下
        path: 'problems',
        name: 'admin-problems-section',
        meta: {
          title: '题目管理',
          titleKey: 'nav.problemsManage',
          icon: 'Collection',
          roles: ['admin', 'tutor'],
        },
        children: [
          {
            path: '',
            name: 'problem-mine',
            component: () => import('@/views/problems/ProblemMineView.vue'),
            meta: {
              title: '题目管理',
              titleKey: 'nav.problemsManage',
              icon: 'Collection',
              roles: ['admin', 'tutor'],
              requiresAuth: true,
            },
          },
          {
            // 第 1 步：基础信息与题面（新建 = 创建草稿；成功后 replace 进入第 2 步）
            path: 'new',
            name: 'problem-create',
            component: () => import('@/views/problems/ProblemStatementView.vue'),
            meta: {
              title: '创建题目',
              titleKey: 'problems.create.title',
              requiresAuth: true,
              hidden: true,
              contextPage: true,
              breadcrumbParent: { titleKey: 'nav.problemsManage', path: '/admin/problems' },
            },
          },
          {
            // 兼容旧链接：编辑入口统一落到第 1 步（题面）
            path: ':id/edit',
            redirect: (to) => `/admin/problems/${String(to.params.id)}/edit/statement`,
          },
          {
            // 三步发布流拆为三个页面：步骤间用路由跳转（可直达 / 刷新保持位置）
            // 第 1 步：题面
            path: ':id/edit/statement',
            name: 'problem-edit-statement',
            component: () => import('@/views/problems/ProblemStatementView.vue'),
            meta: {
              title: '编辑题目',
              titleKey: 'problems.create.editTitle',
              requiresAuth: true,
              hidden: true,
              contextPage: true,
              breadcrumbParent: { titleKey: 'nav.problemsManage', path: '/admin/problems' },
            },
          },
          {
            // 第 2 步：样例与测试点
            path: ':id/edit/cases',
            name: 'problem-edit-cases',
            component: () => import('@/views/problems/ProblemCasesView.vue'),
            meta: {
              title: '样例与测试点',
              titleKey: 'problems.wizard.cases',
              requiresAuth: true,
              hidden: true,
              contextPage: true,
              breadcrumbParent: { titleKey: 'nav.problemsManage', path: '/admin/problems' },
            },
          },
          {
            // 第 3 步：验题与发布
            path: ':id/edit/verify',
            name: 'problem-edit-verify',
            component: () => import('@/views/problems/ProblemVerifyView.vue'),
            meta: {
              title: '验题与发布',
              titleKey: 'problems.wizard.verifyPublish',
              requiresAuth: true,
              hidden: true,
              contextPage: true,
              breadcrumbParent: { titleKey: 'nav.problemsManage', path: '/admin/problems' },
            },
          },
          {
            // 管理后台只读预览：不进前台写题页（无编辑器 / 提交 / 提交记录）
            path: ':id/preview',
            name: 'problem-preview',
            component: () => import('@/views/problems/ProblemPreviewView.vue'),
            meta: {
              title: '题目预览',
              titleKey: 'problems.preview.title',
              requiresAuth: true,
              hidden: true,
              contextPage: true,
              breadcrumbParent: { titleKey: 'nav.problemsManage', path: '/admin/problems' },
            },
          },
        ],
      },
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
      {
        // 标签管理：题库标签的新建 / 修改 / 归档（docs/contracts/problems.md /admin/tags*）
        path: 'tags',
        name: 'admin-tags',
        component: () => import('@/views/admin/AdminTagsView.vue'),
        meta: { title: '标签管理', titleKey: 'nav.tags', icon: 'PriceTag', roles: ['admin'] },
      },
    ],
  },
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
        },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  // 路由切换回到页顶（长列表 / 长表单跨页导航体验一致）
  scrollBehavior: () => ({ top: 0 }),
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
    {
      // 验题邀请落地页：凭链接令牌提交验题代码（公开，登录后回到本页）
      path: '/verify/:token',
      name: 'verify-invite',
      component: () => import('@/views/problems/VerifyInviteView.vue'),
      meta: { title: '验题邀请', titleKey: 'problems.verify.title', public: true },
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
  // 站点名来自 GET /site-config（stores/app），未加载完成时回退 PigeonOJ
  const siteName = useAppStore().siteConfig.name || 'PigeonOJ'
  document.title = title ? `${title} · ${siteName}` : siteName
}

/** 站点配置异步加载完成后刷新标签标题（App.vue watch 调用）。 */
export function refreshDocumentTitle() {
  setDocumentTitle(router.currentRoute.value.meta)
}

router.afterEach((to) => setDocumentTitle(to.meta))
window.addEventListener('pigeonoj:locale-change', () =>
  setDocumentTitle(router.currentRoute.value.meta),
)

export default router
