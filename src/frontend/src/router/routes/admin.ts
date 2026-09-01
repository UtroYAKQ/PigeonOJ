import type { RouteRecordRaw } from 'vue-router'

import { useUserStore } from '@/stores/user'

/**
 * 管理后台路由（hidden：不在前台侧栏显示；入口在头像菜单）。
 * tutor 仅见「题目管理」，admin 见全部区块。
 */
export const adminRoutes: RouteRecordRaw[] = [
  {
    path: 'admin',
    redirect: () => {
      const userStore = useUserStore()
      return userStore.hasAnyRole(['admin']) ? '/admin/users' : '/admin/problems'
    },
    meta: {
      title: '管理后台',
      titleKey: 'nav.admin',
      icon: 'Monitor',
      roles: ['admin', 'tutor'],
      hidden: true,
    },
    children: [
      {
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
            path: ':id/edit',
            redirect: (to) => `/admin/problems/${String(to.params.id)}/edit/statement`,
          },
          {
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
        path: 'problem-sets',
        name: 'admin-problem-sets-section',
        meta: {
          title: '题单管理',
          titleKey: 'nav.problemSetsManage',
          icon: 'Document',
          roles: ['admin', 'tutor'],
        },
        children: [
          {
            path: '',
            name: 'admin-problem-sets',
            component: () => import('@/views/admin/AdminProblemSetsView.vue'),
            meta: {
              title: '题单管理',
              titleKey: 'nav.problemSetsManage',
              icon: 'Document',
              roles: ['admin', 'tutor'],
              requiresAuth: true,
            },
          },
          {
            path: ':id',
            name: 'admin-problem-set-detail',
            component: () => import('@/views/admin/AdminProblemSetDetailView.vue'),
            meta: {
              title: '题单详情',
              titleKey: 'problemSets.detail.title',
              roles: ['admin', 'tutor'],
              requiresAuth: true,
              hidden: true,
              contextPage: true,
            },
          },
          {
            // 题单管理内的题目预览（只读题面，不进入写题页 / 不跳题库）
            // 面包屑：管理后台 / 题单管理 / 题单详情 / 题目预览（父级动态解析到当前题单详情）
            // 参数命名与前台题单上下文一致：:setId=题单 :problemId=题目（预览组件按上下文取参）
            path: ':setId/problems/:problemId/preview',
            name: 'admin-problem-set-problem-preview',
            component: () => import('@/views/problems/ProblemPreviewView.vue'),
            meta: {
              title: '题目预览',
              titleKey: 'problems.preview.title',
              roles: ['admin', 'tutor'],
              requiresAuth: true,
              hidden: true,
              contextPage: true,
              breadcrumbParent: {
                titleKey: 'problemSets.detail.title',
                path: (route) => `/admin/problem-sets/${String(route.params.setId)}`,
              },
            },
          },
        ],
      },
      {
        path: 'contests',
        name: 'admin-contests',
        component: () => import('@/views/admin/AdminContestsView.vue'),
        meta: {
          title: '比赛管理',
          titleKey: 'nav.contestsManage',
          icon: 'Trophy',
          roles: ['admin', 'tutor'],
        },
      },
      {
        path: 'contests/create',
        name: 'admin-contest-create',
        component: () => import('@/views/admin/AdminContestBasicView.vue'),
        meta: {
          title: '创建比赛',
          titleKey: 'contests.list.createTitle',
          roles: ['admin', 'tutor'],
          requiresAuth: true,
          hidden: true,
          contextPage: true,
          breadcrumbParent: { titleKey: 'nav.contestsManage', path: '/admin/contests' },
        },
      },
      {
        path: 'contests/:cid/edit/basic',
        name: 'admin-contest-edit-basic',
        component: () => import('@/views/admin/AdminContestBasicView.vue'),
        meta: {
          title: '编辑比赛',
          titleKey: 'contests.list.editTitle',
          roles: ['admin', 'tutor'],
          requiresAuth: true,
          hidden: true,
          contextPage: true,
          breadcrumbParent: { titleKey: 'nav.contestsManage', path: '/admin/contests' },
        },
      },
      {
        path: 'contests/:cid/edit/problems',
        name: 'admin-contest-edit-problems',
        component: () => import('@/views/admin/AdminContestArrangeView.vue'),
        meta: {
          title: '编排题目',
          titleKey: 'contests.wizard.arrange',
          roles: ['admin', 'tutor'],
          requiresAuth: true,
          hidden: true,
          contextPage: true,
          breadcrumbParent: { titleKey: 'nav.contestsManage', path: '/admin/contests' },
        },
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
        path: 'tags',
        name: 'admin-tags',
        component: () => import('@/views/admin/AdminTagsView.vue'),
        meta: { title: '标签管理', titleKey: 'nav.tags', icon: 'PriceTag', roles: ['admin'] },
      },
    ],
  },
]
