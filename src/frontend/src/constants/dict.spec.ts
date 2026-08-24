import { beforeAll, describe, expect, it } from 'vitest'

import { setLocale } from '@/i18n'
import {
  LOG_LEVEL,
  REPORT_STATUS,
  REPORT_TYPE,
  ROLE_NAME,
  SANDBOX_STATUS,
  USER_STATUS,
  configCategories,
} from './dict'

describe('constants/dict（随 locale 动态翻译）', () => {
  beforeAll(() => {
    setLocale('zh-CN')
  })

  it('角色名映射', () => {
    expect(ROLE_NAME.admin).toBe('系统管理员')
    expect(ROLE_NAME.tutor).toBe('导师')
    expect(ROLE_NAME.user).toBe('普通用户')
  })

  it('用户状态映射含标签色', () => {
    expect(USER_STATUS.active).toEqual({ label: '正常', tag: 'success' })
    expect(USER_STATUS.frozen.tag).toBe('warning')
    expect(USER_STATUS.banned.tag).toBe('danger')
    expect(USER_STATUS.deleted.tag).toBe('info')
  })

  it('未知状态键回退 info 标签', () => {
    const unknown = (USER_STATUS as Record<string, { label: string; tag: string }>).whatever
    expect(unknown.tag).toBe('info')
  })

  it('举报类型 / 举报状态 / 日志级别 / 沙箱状态', () => {
    expect(REPORT_TYPE.post).toBe('帖子')
    expect(REPORT_STATUS.pending).toEqual({ label: '待处理', tag: 'warning' })
    expect(LOG_LEVEL.error.tag).toBe('danger')
    expect(SANDBOX_STATUS.online.label).toBe('在线')
    expect(SANDBOX_STATUS.offline.tag).toBe('info')
  })

  it('配置分类返回全部 7 个域', () => {
    const categories = configCategories()
    expect(categories.map((c) => c.value)).toEqual([
      'site',
      'auth_email',
      'team',
      'contest',
      'sandbox',
      'log',
      'community',
    ])
    expect(categories[0].label).toBe('站点配置')
  })

  it('切换语言后字典即时更新', () => {
    try {
      setLocale('en-US')
      expect(ROLE_NAME.admin).toBe('Administrator')
      expect(USER_STATUS.banned.label).toBe('Banned')
      expect(REPORT_TYPE.post).toBe('Post')
    } finally {
      setLocale('zh-CN')
    }
  })
})
