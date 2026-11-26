import type { RouteLocationNormalizedLoaded, RouteRecordRaw } from 'vue-router'

/**
 * 题解页路由工厂（docs/contracts/community.md「官方题解」/ frontend.md「路由上下文隔离」）。
 *
 * 同一题解页面被多个业务上下文复用（题库 / 题单 / 比赛 / 组织）时，每个上下文在
 * 自己的 URL 前缀下声明独立路由实例，写题页「题解」按钮只在当前上下文内跳转；
 * 团队上下文（快照题裸路径拦截）不接入。路由顺序：列表 / 新建 / 详情 / 编辑。
 */
export interface SolutionContextDef {
  /** 相对父级区块的题目详情 path（含参数占位，如 ':setId/problems/:problemId'） */
  problemPath: string
  /** 路由 name 前缀（上下文内唯一，如 'problem-set'） */
  namePrefix: string
  /** 题目详情页路径构造器（面包屑父级回跳） */
  problemRoutePath: (route: RouteLocationNormalizedLoaded) => string
}

export function buildSolutionRoutes(def: SolutionContextDef): RouteRecordRaw[] {
  const solutionsPath = `${def.problemPath}/solutions`
  const problemCrumb = {
    titleKey: 'problems.detail.title',
    path: def.problemRoutePath,
  }
  const listCrumb = {
    titleKey: 'problems.solutions.title',
    path: (route: RouteLocationNormalizedLoaded) => `${def.problemRoutePath(route)}/solutions`,
  }
  return [
    {
      path: solutionsPath,
      name: `${def.namePrefix}-solutions`,
      component: () => import('@/views/community/ProblemSolutionsView.vue'),
      meta: {
        title: '题解',
        titleKey: 'problems.solutions.title',
        requiresAuth: true,
        hidden: true,
        contextPage: true,
        keepAlive: true,
        breadcrumbParent: problemCrumb,
      },
    },
    {
      // 写题解（表单页，不缓存，保证进出数据新鲜）
      path: `${solutionsPath}/new`,
      name: `${def.namePrefix}-solution-new`,
      component: () => import('@/views/community/SolutionEditorView.vue'),
      meta: {
        title: '写题解',
        titleKey: 'problems.solutions.createTitle',
        requiresAuth: true,
        hidden: true,
        contextPage: true,
        breadcrumbParent: [problemCrumb, listCrumb],
      },
    },
    {
      path: `${solutionsPath}/:solutionId`,
      name: `${def.namePrefix}-solution-detail`,
      component: () => import('@/views/community/SolutionDetailView.vue'),
      meta: {
        title: '题解详情',
        titleKey: 'problems.solutions.detailTitle',
        requiresAuth: true,
        hidden: true,
        contextPage: true,
        keepAlive: true,
        breadcrumbParent: [problemCrumb, listCrumb],
      },
    },
    {
      path: `${solutionsPath}/:solutionId/edit`,
      name: `${def.namePrefix}-solution-edit`,
      component: () => import('@/views/community/SolutionEditorView.vue'),
      meta: {
        title: '编辑题解',
        titleKey: 'problems.solutions.editTitle',
        requiresAuth: true,
        hidden: true,
        contextPage: true,
        breadcrumbParent: [problemCrumb, listCrumb],
      },
    },
  ]
}
