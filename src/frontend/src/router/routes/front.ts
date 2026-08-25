import type { RouteRecordRaw } from 'vue-router'

/**
 * 前台布局子路由（侧边栏菜单数据源）。
 * meta.titleKey 驱动侧栏 / 浏览器标题；meta.hidden 从侧栏隐藏。
 */
export const frontRoutes: RouteRecordRaw[] = [
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
]
