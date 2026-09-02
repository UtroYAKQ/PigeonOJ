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
        meta: { title: '题库', titleKey: 'nav.problems', icon: 'Collection', keepAlive: true },
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
          keepAlive: true,
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
          keepAlive: true,
          // 面包屑：题库 / 题目详情 / 评测结果（父级动态解析到当前题目详情页）
          breadcrumbParent: {
            titleKey: 'problems.detail.title',
            path: (route) => `/problems/${String(route.params.problemId)}`,
          },
        },
      },
    ],
  },
  {
    path: 'problem-sets',
    redirect: '/problem-sets/list',
    meta: { title: '题单', titleKey: 'nav.problemSets', icon: 'Document' },
    children: [
      {
        path: 'list',
        name: 'problem-sets',
        component: () => import('@/views/problemsets/ProblemSetListView.vue'),
        meta: { title: '题单', titleKey: 'nav.problemSets', icon: 'Document', keepAlive: true },
      },
      {
        path: ':id',
        name: 'problem-set-detail',
        component: () => import('@/views/problemsets/ProblemSetDetailView.vue'),
        meta: {
          title: '题单详情',
          titleKey: 'problemSets.detail.title',
          hidden: true,
          contextPage: true,
          keepAlive: true,
        },
      },
      {
        // 题单上下文内的写题页：复用题库详情组件，交题 / 评测结果均不跳出题单。
        // 面包屑：题单 / 题单详情 / 题目详情（父级动态解析到当前题单详情页）
        path: ':setId/problems/:problemId',
        name: 'problem-set-problem',
        component: () => import('@/views/problems/ProblemDetailView.vue'),
        meta: {
          title: '题目详情',
          titleKey: 'problems.detail.title',
          requiresAuth: true,
          hidden: true,
          contextPage: true,
          keepAlive: true,
          breadcrumbParent: {
            titleKey: 'problemSets.detail.title',
            path: (route) => `/problem-sets/${String(route.params.setId)}`,
          },
        },
      },
      {
        path: ':setId/problems/:problemId/submissions/:id',
        name: 'problem-set-submission',
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
              titleKey: 'problemSets.detail.title',
              path: (route) => `/problem-sets/${String(route.params.setId)}`,
            },
            {
              titleKey: 'problems.detail.title',
              path: (route) =>
                `/problem-sets/${String(route.params.setId)}/problems/${String(route.params.problemId)}`,
            },
          ],
        },
      },
    ],
  },
  {
    path: 'contests',
    redirect: '/contests/list',
    meta: { title: '比赛', titleKey: 'nav.contests', icon: 'Trophy' },
    children: [
      {
        path: 'list',
        name: 'contests',
        component: () => import('@/views/contests/ContestListView.vue'),
        meta: { title: '比赛', titleKey: 'nav.contests', icon: 'Trophy', keepAlive: true },
      },
      {
        path: ':id',
        name: 'contest-detail',
        component: () => import('@/views/contests/ContestDetailView.vue'),
        meta: {
          title: '比赛详情',
          titleKey: 'contests.detail.title',
          hidden: true,
          contextPage: true,
          keepAlive: true,
        },
      },
      {
        // 比赛上下文内的写题页：复用题库详情组件，交题 / 评测结果均不跳出比赛
        // 面包屑：比赛 / 比赛详情 / 题目详情（父级动态解析到当前比赛详情页）
        path: ':cid/problems/:problemId',
        name: 'contest-problem',
        component: () => import('@/views/problems/ProblemDetailView.vue'),
        meta: {
          title: '题目详情',
          titleKey: 'problems.detail.title',
          requiresAuth: true,
          hidden: true,
          contextPage: true,
          keepAlive: true,
          breadcrumbParent: {
            titleKey: 'contests.detail.title',
            path: (route) => `/contests/${String(route.params.cid)}`,
          },
        },
      },
      {
        path: ':cid/problems/:problemId/submissions/:id',
        name: 'contest-submission',
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
              titleKey: 'contests.detail.title',
              path: (route) => `/contests/${String(route.params.cid)}`,
            },
            {
              titleKey: 'problems.detail.title',
              path: (route) =>
                `/contests/${String(route.params.cid)}/problems/${String(route.params.problemId)}`,
            },
          ],
        },
      },
      {
        // 比赛提交记录的评测结果：经比赛统一入口端点（赛后开放），
        // 不跳出比赛上下文；面包屑回比赛详情页
        path: ':cid/submissions/:sid',
        name: 'contest-submission-detail',
        component: () => import('@/views/contests/ContestSubmissionView.vue'),
        meta: {
          title: '评测结果',
          titleKey: 'problems.submission.title',
          requiresAuth: true,
          hidden: true,
          contextPage: true,
          keepAlive: true,
          breadcrumbParent: {
            titleKey: 'contests.detail.title',
            path: (route) => `/contests/${String(route.params.cid)}`,
          },
        },
      },
    ],
  },
  {
    path: 'teams',
    redirect: '/teams/mine',
    meta: { title: '团队', titleKey: 'nav.teams', icon: 'UserFilled' },
    children: [
      {
        path: 'mine',
        name: 'teams',
        component: () => import('@/views/teams/TeamListView.vue'),
        meta: {
          title: '团队',
          titleKey: 'nav.teams',
          icon: 'UserFilled',
          requiresAuth: true,
          keepAlive: true,
        },
      },
      {
        path: 'invites/:token',
        name: 'team-invite',
        component: () => import('@/views/teams/TeamInviteView.vue'),
        meta: {
          title: '团队邀请',
          titleKey: 'teams.invite.title',
          hidden: true,
          contextPage: true,
        },
      },
      {
        path: ':id',
        name: 'team-detail',
        component: () => import('@/views/teams/TeamDetailView.vue'),
        meta: {
          title: '团队详情',
          titleKey: 'teams.detail.title',
          requiresAuth: true,
          hidden: true,
          contextPage: true,
          keepAlive: true,
          breadcrumbParent: { titleKey: 'nav.teams', path: '/teams/mine' },
        },
      },
    ],
  },
]
