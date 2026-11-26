import type { RouteRecordRaw } from 'vue-router'

import { buildSolutionRoutes } from './solutions'

/**
 * 个人面板路由（第三区块）：前台/后台之外的个人空间。
 * 收纳账号设置（个人资料 / 安全设置 / 会话管理）与组织中心（/me/orgs/*）。
 * 区块本身在前台侧栏可见作入口，进入后侧栏切换为个人面板菜单（见 SideMenu.vue）。
 */
export const meRoutes: RouteRecordRaw[] = [
  {
    path: 'me',
    redirect: '/me/profile',
    meta: {
      title: '个人面板',
      titleKey: 'nav.me',
      icon: 'User',
      hidden: true,
      requiresAuth: true,
    },
    children: [
      {
        path: 'profile',
        name: 'me-profile',
        component: () => import('@/views/user/ProfileView.vue'),
        meta: { title: '个人资料', titleKey: 'user.profile', icon: 'User', requiresAuth: true },
      },
      {
        path: 'security',
        name: 'me-security',
        component: () => import('@/views/user/SecurityView.vue'),
        meta: { title: '安全设置', titleKey: 'user.security', icon: 'Lock', requiresAuth: true },
      },
      {
        path: 'sessions',
        name: 'me-sessions',
        component: () => import('@/views/user/SessionsView.vue'),
        meta: {
          title: '会话管理',
          titleKey: 'user.sessions',
          icon: 'Odometer',
          requiresAuth: true,
          keepAlive: true,
        },
      },
      {
        // 组织中心（docs/contracts/orgs.md）：组织 = 多机构租户单元；
        // 团队挂在组织下，组织题库为封闭上下文（题目编辑复用题库统一端点，仅创建走组织端点）
        path: 'orgs',
        redirect: '/me/orgs/mine',
        meta: { title: '组织', titleKey: 'nav.orgs', icon: 'OfficeBuilding', requiresAuth: true },
        children: [
          {
            path: 'mine',
            name: 'me-orgs',
            component: () => import('@/views/orgs/OrgListView.vue'),
            meta: {
              title: '组织中心',
              titleKey: 'nav.orgs',
              icon: 'OfficeBuilding',
              requiresAuth: true,
              keepAlive: true,
            },
          },
          {
            path: ':id',
            name: 'me-org-detail',
            component: () => import('@/views/orgs/OrgDetailView.vue'),
            meta: {
              title: '组织详情',
              titleKey: 'orgs.detail.title',
              requiresAuth: true,
              hidden: true,
              contextPage: true,
              keepAlive: true,
              breadcrumbParent: { titleKey: 'nav.orgs', path: '/me/orgs/mine' },
            },
          },
          {
            // 组织题目创建向导（第一步题面）：POST /orgs/{orgId}/problems（org_member）
            path: ':orgId/problems/new',
            name: 'me-org-problem-create',
            component: () => import('@/views/problems/ProblemStatementView.vue'),
            meta: {
              title: '创建题目',
              titleKey: 'problems.create.title',
              requiresAuth: true,
              hidden: true,
              contextPage: true,
              breadcrumbParent: {
                titleKey: 'orgs.detail.title',
                path: (route) => `/me/orgs/${String(route.params.orgId)}`,
              },
            },
          },
          {
            // 组织题目编辑向导：题面 / 测试点 / 验题复用题库统一端点（org 成员过权限门）
            path: ':orgId/problems/:problemId/edit/statement',
            name: 'me-org-problem-edit-statement',
            component: () => import('@/views/problems/ProblemStatementView.vue'),
            meta: {
              title: '编辑题目',
              titleKey: 'problems.create.editTitle',
              requiresAuth: true,
              hidden: true,
              contextPage: true,
              breadcrumbParent: {
                titleKey: 'orgs.detail.title',
                path: (route) => `/me/orgs/${String(route.params.orgId)}`,
              },
            },
          },
          {
            path: ':orgId/problems/:problemId/edit/cases',
            name: 'me-org-problem-edit-cases',
            component: () => import('@/views/problems/ProblemCasesView.vue'),
            meta: {
              title: '样例与测试点',
              titleKey: 'problems.wizard.cases',
              requiresAuth: true,
              hidden: true,
              contextPage: true,
              breadcrumbParent: {
                titleKey: 'orgs.detail.title',
                path: (route) => `/me/orgs/${String(route.params.orgId)}`,
              },
            },
          },
          {
            path: ':orgId/problems/:problemId/edit/verify',
            name: 'me-org-problem-edit-verify',
            component: () => import('@/views/problems/ProblemVerifyView.vue'),
            meta: {
              title: '验题与发布',
              titleKey: 'problems.wizard.verifyPublish',
              requiresAuth: true,
              hidden: true,
              contextPage: true,
              breadcrumbParent: {
                titleKey: 'orgs.detail.title',
                path: (route) => `/me/orgs/${String(route.params.orgId)}`,
              },
            },
          },
          {
            // 组织题目作答页（组织上下文）：复用题库详情组件，读 / 交题 / 自测走题库
            // 裸路径端点（组织成员经 can_manage 放行，docs/contracts/orgs.md「组织成员
            // 可对组织题交题/自测」）；评测结果落在 /submissions/:id 保持组织上下文。
            path: ':orgId/problems/:problemId',
            name: 'me-org-problem',
            component: () => import('@/views/problems/ProblemDetailView.vue'),
            meta: {
              title: '题目详情',
              titleKey: 'problems.detail.title',
              requiresAuth: true,
              hidden: true,
              contextPage: true,
              keepAlive: true,
              breadcrumbParent: {
                titleKey: 'orgs.detail.title',
                path: (route) => `/me/orgs/${String(route.params.orgId)}`,
              },
            },
          },
          {
            // 组织题目评测结果（组织上下文内不跳出）
            path: ':orgId/problems/:problemId/submissions/:id',
            name: 'me-org-problem-submission',
            component: () => import('@/views/problems/SubmissionView.vue'),
            meta: {
              title: '评测结果',
              titleKey: 'problems.submission.title',
              requiresAuth: true,
              hidden: true,
              contextPage: true,
              keepAlive: true,
              breadcrumbParent: [
                {
                  titleKey: 'orgs.detail.title',
                  path: (route) => `/me/orgs/${String(route.params.orgId)}`,
                },
                {
                  titleKey: 'problems.detail.title',
                  path: (route) =>
                    `/me/orgs/${String(route.params.orgId)}/problems/${String(route.params.problemId)}`,
                },
              ],
            },
          },
          // 题解页（组织上下文；组织成员经题目可见性门控读写）
          ...buildSolutionRoutes({
            problemPath: ':orgId/problems/:problemId',
            namePrefix: 'me-org',
            problemRoutePath: (route) =>
              `/me/orgs/${String(route.params.orgId)}/problems/${String(route.params.problemId)}`,
          }),
        ],
      },
    ],
  },
]
