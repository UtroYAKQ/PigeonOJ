import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createI18n } from 'vue-i18n'
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios'

import AdminOrgDetailView from '@/views/admin/AdminOrgDetailView.vue'
import { httpClient } from '@/api/http'

// 轻量 mock stores / feedback，避免重依赖
vi.mock('@/stores/user', () => ({
  useUserStore: () => ({ user: { id: 'u1', nickname: 'Admin' }, isAdmin: true }),
}))
vi.mock('@/utils/feedback', () => ({
  message: { error: vi.fn(), success: vi.fn(), warning: vi.fn() },
  dialog: { warning: vi.fn(), error: vi.fn() },
}))

type Res = { code: number; message: string; data: unknown }
function envelope(data: unknown): Res {
  return { code: 0, message: 'ok', data }
}

function makeAdapter(handler: (config: { url?: string }) => Res) {
  return async (
    config: InternalAxiosRequestConfig & { headers: InternalAxiosRequestConfig['headers'] },
  ): Promise<AxiosResponse> => ({
    status: 200,
    statusText: 'OK',
    headers: {},
    data: handler(config),
    config: config as unknown as InternalAxiosRequestConfig,
  })
}

async function flush() {
  for (let i = 0; i < 8; i++) {
    await Promise.resolve()
    await new Promise((r) => setTimeout(r, 0))
  }
}

const messages = {
  'admin.orgs.detailTitle': '组织详情',
  'admin.orgs.tabMembers': '成员',
  'admin.orgs.membersEmpty': '暂无成员',
  'admin.orgs.memberCount': '成员数',
  'admin.orgs.teamCount': '团队数',
  'admin.orgs.createdAt': '创建时间',
  'admin.orgs.statusActive': '正常',
  'admin.orgs.role': '角色',
  'orgs.role.admin': '管理员',
  'orgs.role.member': '成员',
  'orgs.members.note': '备注',
  'orgs.members.joinedAt': '加入时间',
  'orgs.members.search': '搜索',
  'orgs.members.grantAdmin': '设为组织管理员',
  'orgs.members.revokeAdmin': '取消组织管理员',
  'orgs.members.kick': '移出',
  'action.operations': '操作',
  'common.operationFailed': '操作失败',
  'common.loadFailed': '加载失败',
  'action.refresh': '刷新',
  'admin.orgs.loadFailed': '加载失败',
  'problems.list.name': '题目名称',
  'admin.teams.team': '团队',
  'admin.orgs.teamVisibility': '可见性',
  'teams.settings.visibilityPublic': '公开',
  'teams.settings.visibilityPrivate': '私有',
  'admin.orgs.tabTeams': '团队',
  'admin.orgs.tabProblems': '题目',
  'orgs.problems.draftBox': '只看草稿',
  'orgs.problems.empty': '暂无题目',
  'problems.manage.verifiedTag': '已验题',
  'problems.manage.unverifiedTag': '未验题',
  'problems.manage.reverifyTag': '需重新验题',
  'problems.list.difficulty': '难度',
  'problems.list.limits': '限制',
  'problems.list.passRate': '通过率',
  'problems.manage.shareTitle': '发布',
  'orgs.teams.search': '搜索团队',
  'orgs.problems.search': '搜索题目',
}

describe('AdminOrgDetailView 成员 tab', () => {
  let piniaMock: ReturnType<typeof createPinia>
  beforeEach(() => {
    piniaMock = createPinia()
    httpClient.defaults.adapter = makeAdapter(({ url }) => {
      if (url?.includes('/members')) {
        return envelope({
          items: [
            {
              user_id: 'm1',
              nickname: '张三',
              avatar_url: null,
              status: 'active',
              joined_at: '2026-01-01T00:00:00Z',
              is_admin: true,
              note: null,
            },
          ],
          total: 1,
          page: 1,
          page_size: 20,
        })
      }
      if (url?.includes('/admin/orgs/')) {
        return envelope({
          id: 'org1',
          name: '测试组织',
          description: 'desc',
          avatar_url: null,
          created_at: '2026-01-01T00:00:00Z',
          member_count: 1,
          team_count: 0,
          created_by: 'u1',
          status: 'active',
          disbanded_at: null,
        })
      }
      return envelope({ items: [], total: 0, page: 1, page_size: 20 })
    })
  })

  it('挂载后自动加载成员并渲染昵称', async () => {
    const i18n = createI18n({
      legacy: false,
      locale: 'zh-CN',
      messages: { 'zh-CN': messages },
    })
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/admin/orgs/:id',
          name: 'admin-org-detail',
          component: { template: '<div />' },
        },
      ],
    })
    router.push('/admin/orgs/org1')
    await router.isReady()

    const app = createApp(AdminOrgDetailView)
    app.use(piniaMock)
    app.use(i18n)
    app.use(router)
    const el = document.createElement('div')
    document.body.appendChild(el)
    const vm = app.mount(el)
    await flush()
    void vm

    // 成员 tab 为默认 active，应已触发 loadMembers
    expect(el.textContent).toContain('张三')
    app.unmount()
    el.remove()
  })
})