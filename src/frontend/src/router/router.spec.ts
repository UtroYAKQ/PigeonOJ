import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import type { RouteLocationNormalizedLoaded, RouteRecordRaw } from 'vue-router'

import { frontRoutes } from './routes/front'
import { adminRoutes } from './routes/admin'
import { meRoutes } from './routes/me'
import { publicRoutes } from './routes/public'
import { buildCrumbs } from './crumbs'
import { registerGuards } from './guards'
import { useUserStore } from '@/stores/user'

// feedback 的 discrete API 在模块导入期挂载且依赖已激活的 pinia（守卫运行时动态
// 导入同样命中 mock），测试统一桩掉，顺便断言守卫的无权限提示
vi.mock('@/utils/feedback', () => ({
  message: { warning: vi.fn(), success: vi.fn(), error: vi.fn(), info: vi.fn() },
  dialog: { warning: vi.fn() },
}))

// 视图组件在导入期会拉起 monaco / naive-ui 等重依赖，路由匹配测试只关心
// 路径 → 记录的解析结果，统一替换为空组件桩
function stubComponents(routes: RouteRecordRaw[]): RouteRecordRaw[] {
  return routes.map((route) => {
    const stubbed: RouteRecordRaw = { ...route }
    if (route.component) {
      stubbed.component = () => Promise.resolve({ template: '<div />' })
    }
    if (route.children) stubbed.children = stubComponents(route.children)
    return stubbed
  })
}

function buildRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/',
        component: () => Promise.resolve({ template: '<div />' }),
        children: stubComponents([...frontRoutes, ...adminRoutes, ...meRoutes]),
      },
      ...stubComponents(publicRoutes),
      { path: '/:pathMatch(.*)*', redirect: '/' },
    ],
  })
}

const cases: Array<[string, string]> = [
  ['/problems', 'problems'],
  ['/problems/list', 'problems'],
  ['/problems/5', 'problem-detail'],
  ['/problems/5/submissions/9', 'submission-detail'],
  ['/problem-sets', 'problem-sets'],
  ['/problem-sets/3', 'problem-set-detail'],
  ['/problem-sets/3/problems/5', 'problem-set-problem'],
  ['/problem-sets/3/problems/5/submissions/9', 'problem-set-submission'],
  ['/contests', 'contests'],
  ['/contests/3', 'contest-detail'],
  ['/contests/3/problems/5', 'contest-problem'],
  ['/contests/3/problems/5/submissions/9', 'contest-submission'],
  ['/contests/3/submissions/9', 'contest-submission-detail'],
  ['/teams', 'teams'],
  ['/teams/mine', 'teams'],
  ['/teams/invites/tok123', 'team-invite'],
  ['/teams/5', 'team-detail'],
  ['/teams/5/sets/new', 'team-set-create'],
  ['/teams/5/sets/7', 'team-set-detail'],
  ['/teams/5/sets/7/arrange', 'team-set-arrange'],
  ['/teams/5/sets/7/problems/9', 'team-set-problem'],
  ['/teams/5/contests/3', 'team-contest-detail'],
  ['/teams/5/contests/3/tools', 'team-contest-tools'],
  ['/teams/5/contests/3/problems/9', 'team-contest-problem'],
  ['/teams/5/contests/3/problems/9/submissions/1', 'team-contest-problem-submission'],
  ['/teams/5/contests/3/submissions/1', 'team-contest-submission-detail'],
  ['/teams/5/problems/9', 'team-problem'],
  ['/teams/5/problems/9/edit/statement', 'team-problem-edit-statement'],
  ['/admin', 'admin-users'],
  ['/admin/problems', 'problem-mine'],
  ['/admin/problems/new', 'problem-create'],
  ['/admin/problems/3/edit', 'problem-edit-statement'],
  ['/admin/problems/3/edit/cases', 'problem-edit-cases'],
  ['/admin/problems/3/submissions', 'problem-submissions'],
  ['/admin/problems/3/submissions/8', 'problem-submission-detail'],
  ['/admin/problem-sets', 'admin-problem-sets'],
  ['/admin/problem-sets/3', 'admin-problem-set-detail'],
  ['/admin/problem-sets/3/problems/5/preview', 'admin-problem-set-problem-preview'],
  ['/admin/contests', 'admin-contests'],
  ['/admin/contests/create', 'admin-contest-create'],
  ['/admin/contests/3/tools', 'admin-contest-tools'],
  ['/admin/contests/3/edit/problems', 'admin-contest-edit-problems'],
  ['/admin/teams/3', 'admin-team-detail'],
  ['/admin/orgs/3', 'admin-org-detail'],
  ['/admin/users', 'admin-users'],
  ['/admin/users/online', 'admin-online-users'],
  ['/admin/submissions/problems/5/preview', 'admin-submission-problem-preview'],
  ['/admin/submissions/problems/5/submissions/8', 'admin-submission-detail'],
  ['/me', 'me-profile'],
  ['/me/profile', 'me-profile'],
  ['/me/security', 'me-security'],
  ['/me/sessions', 'me-sessions'],
  ['/me/orgs', 'me-orgs'],
  ['/me/orgs/2', 'me-org-detail'],
  ['/me/orgs/2/problems/new', 'me-org-problem-create'],
  ['/me/orgs/2/problems/4/edit/cases', 'me-org-problem-edit-cases'],
  ['/login', 'login'],
  ['/register', 'register'],
  ['/verify/tok', 'verify-invite'],
]

describe('route table matching', () => {
  it('has no duplicate route names', () => {
    const names: string[] = []
    const walk = (rs: RouteRecordRaw[]) => {
      for (const r of rs) {
        if (r.name) names.push(String(r.name))
        if (r.children) walk(r.children)
      }
    }
    walk(frontRoutes)
    walk(adminRoutes)
    walk(meRoutes)
    walk(publicRoutes)
    expect(names).toEqual([...new Set(names)])
  })

  for (const [path, name] of cases) {
    it(`resolves ${path} -> ${name}`, async () => {
      const router = buildRouter()
      await router.push(path)
      await router.isReady()
      expect(router.currentRoute.value.name).toBe(name)
    })
  }

  it('catch-all redirects home', async () => {
    const router = buildRouter()
    await router.push('/nope/xyz')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/')
  })
})

describe('guards', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('未登录访问需登录页：跳登录并携带站内回跳参数', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes: [] })
    registerGuards(router)
    router.addRoute({
      path: '/',
      component: { template: '<div />' },
      children: [
        {
          path: 'problems/:id',
          name: 'problem-detail',
          component: { template: '<div />' },
          meta: { requiresAuth: true },
        },
      ],
    })
    await router.push('/problems/5')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.redirect).toBe('/problems/5')
  })

  it('已登录但角色不足：回首页并弹出无权限提示', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes: [] })
    registerGuards(router)
    router.addRoute({
      path: '/admin',
      component: { template: '<div />' },
      meta: { roles: ['admin'] },
      children: [
        {
          path: 'users',
          name: 'admin-users',
          component: { template: '<div />' },
          meta: { requiresAuth: true },
        },
      ],
    })
    const userStore = useUserStore()
    userStore.initialized = true
    userStore.token = 'tok'
    userStore.user = { id: 1, roles: ['user'] } as never
    await router.push('/admin/users')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/')
    expect(router.currentRoute.value.query.denied).toBeUndefined()
    const { message } = await import('@/utils/feedback')
    expect(message.warning).toHaveBeenCalled()
  })
})

describe('buildCrumbs', () => {
  const translate = (key: string) => key

  function fakeRoute(
    matched: Array<{ path: string; meta?: Record<string, unknown> }>,
    params: Record<string, string> = {},
  ) {
    return { matched, params } as unknown as RouteLocationNormalizedLoaded
  }

  it('首页不产生面包屑（根记录按 path === "/" 排除）', () => {
    const crumbs = buildCrumbs(
      fakeRoute([
        { path: '/' },
        { path: '/', meta: { titleKey: 'nav.home' } },
      ]),
      translate,
    )
    expect(crumbs).toEqual([])
  })

  it('列表页：区块与列表同名校去重，仅一项且无链接', () => {
    const crumbs = buildCrumbs(
      fakeRoute([
        { path: '/' },
        { path: '/problems', meta: { titleKey: 'nav.problems', redirect: '/problems/list' } },
        { path: '/problems/list', meta: { titleKey: 'nav.problems' } },
      ]),
      translate,
    )
    expect(crumbs).toEqual([{ label: 'nav.problems', to: undefined }])
  })

  it('上下文页：breadcrumbParent 父链按序插入当前页之前', () => {
    const crumbs = buildCrumbs(
      fakeRoute(
        [
          { path: '/' },
          { path: '/contests', meta: { titleKey: 'nav.contests' } },
          {
            path: '/contests/:cid/problems/:problemId',
            meta: {
              titleKey: 'problems.detail.title',
              breadcrumbParent: {
                titleKey: 'contests.detail.title',
                path: (r: RouteLocationNormalizedLoaded) => `/contests/${String(r.params.cid)}`,
              },
            },
          },
        ],
        { cid: '3', problemId: '5' },
      ),
      translate,
    )
    expect(crumbs).toEqual([
      { label: 'nav.contests', to: '/contests' },
      { label: 'contests.detail.title', to: '/contests/3' },
      { label: 'problems.detail.title', to: undefined },
    ])
  })
})
