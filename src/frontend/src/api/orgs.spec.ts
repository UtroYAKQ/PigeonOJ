import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from 'axios'

import { httpClient } from './http'
import {
  addOrgMembers,
  createOrg,
  createOrgProblem,
  createOrgTeam,
  disbandOrg,
  getOrg,
  getOrgProblem,
  listMyOrgs,
  listOrgMembers,
  listOrgProblems,
  listOrgTeams,
  removeOrgMember,
  setOrgMemberAdmin,
  setOrgMemberNote,
  updateOrg,
} from './orgs'

const envelope = (data: unknown = null) => ({ code: 0, message: 'ok', data })

const adapterMock = vi.fn()

describe('api/orgs（组织模块端点与载荷，docs/contracts/orgs.md）', () => {
  beforeEach(() => {
    adapterMock.mockReset()
    httpClient.defaults.adapter = adapterMock as unknown as AxiosAdapter
    adapterMock.mockImplementation(async (config: InternalAxiosRequestConfig) => {
      const response: AxiosResponse = {
        status: 200,
        statusText: 'OK',
        headers: {},
        data: envelope(),
        config,
      }
      return response
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  function lastCall(): { url: string; method: string; data?: string } {
    const [config] = adapterMock.mock.calls[adapterMock.mock.calls.length - 1] as [
      InternalAxiosRequestConfig,
    ]
    return {
      url: config.url ?? '',
      method: (config.method ?? 'get').toLowerCase(),
      data: typeof config.data === 'string' ? config.data : undefined,
    }
  }

  it('创建组织走 POST /orgs，携带 admin_user_ids', async () => {
    await createOrg({ name: '组织A', admin_user_ids: ['u1', 'u2'] })
    const { url, method, data } = lastCall()
    expect(method).toBe('post')
    expect(url).toBe('/orgs')
    expect(JSON.parse(data ?? '{}')).toEqual({ name: '组织A', admin_user_ids: ['u1', 'u2'] })
  })

  it('我的组织列表 / 组织详情 / 更新 / 解散的 URL 形态', async () => {
    await listMyOrgs({ page: 2, keyword: '组织' })
    expect(lastCall().url).toBe('/orgs/mine?page=2&keyword=%E7%BB%84%E7%BB%87')

    await getOrg('org-1')
    expect(lastCall()).toMatchObject({ url: '/orgs/org-1', method: 'get' })

    await updateOrg('org-1', { name: '新名' })
    expect(lastCall()).toMatchObject({ url: '/orgs/org-1', method: 'put' })

    await disbandOrg('org-1')
    expect(lastCall()).toMatchObject({ url: '/orgs/org-1', method: 'delete' })
  })

  it('成员管理端点：批量添加 / 移出 / 授撤管理员 / 备注', async () => {
    await addOrgMembers('org-1', ['u1', 'u2'])
    const added = lastCall()
    expect(added).toMatchObject({ url: '/orgs/org-1/members', method: 'post' })
    expect(JSON.parse(added.data ?? '{}')).toEqual({ user_ids: ['u1', 'u2'] })

    await removeOrgMember('org-1', 'u1')
    expect(lastCall()).toMatchObject({ url: '/orgs/org-1/members/u1', method: 'delete' })

    await setOrgMemberAdmin('org-1', 'u1', true)
    const admin = lastCall()
    expect(admin.url).toBe('/orgs/org-1/members/u1/admin')
    expect(JSON.parse(admin.data ?? '{}')).toEqual({ is_admin: true })

    await setOrgMemberNote('org-1', 'u1', null)
    const note = lastCall()
    expect(note.url).toBe('/orgs/org-1/members/u1/note')
    expect(JSON.parse(note.data ?? '{}')).toEqual({ note: null })

    await listOrgMembers('org-1', { keyword: '张', status: 'active' })
    expect(lastCall().url).toBe('/orgs/org-1/members?keyword=%E5%BC%A0&status=active')
  })

  it('组织团队 / 组织题库端点：创建团队 / 团队列表 / 题库列表 / 直建题目 / 题目详情', async () => {
    await createOrgTeam('org-1', { name: '团队A', visibility: 'private' })
    expect(lastCall()).toMatchObject({ url: '/orgs/org-1/teams', method: 'post' })

    await listOrgTeams('org-1', { keyword: 'A' })
    expect(lastCall().url).toBe('/orgs/org-1/teams?keyword=A')

    await listOrgProblems('org-1', { status: 'draft' })
    expect(lastCall().url).toBe('/orgs/org-1/problems?status=draft')

    await createOrgProblem('org-1', {
      title: '题A',
      background: 'bg',
      description: 'desc',
      input_description: 'in',
      output_description: 'out',
    })
    expect(lastCall()).toMatchObject({ url: '/orgs/org-1/problems', method: 'post' })

    await getOrgProblem('org-1', 'p1')
    expect(lastCall()).toMatchObject({ url: '/orgs/org-1/problems/p1', method: 'get' })
  })
})
