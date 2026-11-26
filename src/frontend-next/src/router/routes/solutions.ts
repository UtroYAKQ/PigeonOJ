import type { RouteLocationNormalizedLoaded, RouteRecordRaw } from 'vue-router'

interface CrumbDef {
  titleKey: string
  path: (route: RouteLocationNormalizedLoaded) => string
}

export interface SolutionContextDef {
  /** 题目详情在当前父路由下的相对 path（如 ':setId/problems/:problemId'） */
  problemPath: string
  /** 路由 name 前缀（上下文内唯一） */
  namePrefix: string
  /** 题目详情绝对路径（参数取自当前路由） */
  problemRoutePath: (route: RouteLocationNormalizedLoaded) => string
  /** 上下文父链（列表 / 详情），按层级从外到内 */
  contextParents: CrumbDef[]
}

/**
 * 题解路由（列表 / 新建 / 详情 / 编辑）。
 * 每个题目上下文拥有独立路由实例，所有跳转留在本上下文内。
 */
export function buildSolutionRoutes(def: SolutionContextDef): RouteRecordRaw[] {
  const solutionsPath = (route: RouteLocationNormalizedLoaded) =>
    `${def.problemRoutePath(route)}/solutions`
  const parents = [
    ...def.contextParents,
    { titleKey: 'problems.detail.title', path: def.problemRoutePath },
  ]

  return [
    {
      path: `${def.problemPath}/solutions`,
      name: `${def.namePrefix}-solutions`,
      component: () => import('@/views/community/ProblemSolutionsView.vue'),
      meta: {
        title: '题解',
        titleKey: 'problems.solutions.title',
        requiresAuth: true,
        hidden: true,
        contextPage: true,
        keepAlive: true,
        breadcrumbParent: parents,
      },
    },
    {
      path: `${def.problemPath}/solutions/new`,
      name: `${def.namePrefix}-solution-new`,
      component: () => import('@/views/community/SolutionEditorView.vue'),
      meta: {
        title: '写题解',
        titleKey: 'problems.solutions.createTitle',
        requiresAuth: true,
        hidden: true,
        contextPage: true,
        breadcrumbParent: [
          ...parents,
          { titleKey: 'problems.solutions.title', path: solutionsPath },
        ],
      },
    },
    {
      path: `${def.problemPath}/solutions/:solutionId`,
      name: `${def.namePrefix}-solution-detail`,
      component: () => import('@/views/community/SolutionDetailView.vue'),
      meta: {
        title: '题解详情',
        titleKey: 'problems.solutions.detailTitle',
        requiresAuth: true,
        hidden: true,
        contextPage: true,
        keepAlive: true,
        breadcrumbParent: [
          ...parents,
          { titleKey: 'problems.solutions.title', path: solutionsPath },
        ],
      },
    },
    {
      path: `${def.problemPath}/solutions/:solutionId/edit`,
      name: `${def.namePrefix}-solution-edit`,
      component: () => import('@/views/community/SolutionEditorView.vue'),
      meta: {
        title: '编辑题解',
        titleKey: 'problems.solutions.editTitle',
        requiresAuth: true,
        hidden: true,
        contextPage: true,
        breadcrumbParent: [
          ...parents,
          { titleKey: 'problems.solutions.title', path: solutionsPath },
        ],
      },
    },
  ]
}