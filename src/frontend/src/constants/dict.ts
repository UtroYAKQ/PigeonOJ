/** 由当前 locale 动态生成的展示字典。 */
import type { GlobalRoleCode, ReportType } from '@/types'
import { i18n } from '@/i18n'
export type TagType = 'primary' | 'success' | 'warning' | 'danger' | 'info'
/** Naive UI n-tag 的 type 取值（无 danger，用 error 表达） */
export type NaiveTagType = 'primary' | 'success' | 'warning' | 'error' | 'info' | 'default'
export const toNaiveTagType = (tag: TagType): NaiveTagType => (tag === 'danger' ? 'error' : tag)
const t = (key: string): string =>
  (i18n as unknown as { global: { t: (key: string) => string } }).global.t(key)
/**
 * 按声明的键集生成「随 locale 动态翻译」的键值映射。
 * 必须实现 ownKeys 陷阱：字典在视图里经 Object.keys 枚举生成下拉选项
 * （如管理后台的角色勾选、举报状态筛选），缺陷阱会枚举出空数组导致选项消失。
 */
const labels = <T extends string>(prefix: string, values: readonly T[]) =>
  new Proxy({} as Record<T, string>, {
    get: (_target, key) => t(`${prefix}.${String(key)}`),
    ownKeys: () => [...values],
    getOwnPropertyDescriptor: () => ({ enumerable: true, configurable: true }),
  })
export const ROLE_NAME = labels('user.role', ['admin', 'tutor', 'user'] as const) as Record<
  GlobalRoleCode,
  string
>
const statusProxy = <T extends string>(
  prefix: string,
  values: readonly T[],
  tags: Record<string, TagType>,
) =>
  new Proxy({} as Record<T, { label: string; tag: TagType }>, {
    get: (_target, key) => ({
      label: t(`${prefix}.${String(key)}`),
      tag: tags[String(key)] ?? 'info',
    }),
    ownKeys: () => [...values],
    getOwnPropertyDescriptor: () => ({ enumerable: true, configurable: true }),
  })
export const USER_STATUS = statusProxy(
  'user.status',
  ['active', 'frozen', 'banned', 'deleted'] as const,
  { active: 'success', frozen: 'warning', banned: 'danger', deleted: 'info' },
)
export const REPORT_STATUS = statusProxy(
  'dictionary.reportStatus',
  ['pending', 'handled', 'ignored'] as const,
  { pending: 'warning', handled: 'success', ignored: 'info' },
)
export const LOG_LEVEL = statusProxy('dictionary.logLevel', ['error', 'warning', 'fatal'] as const, {
  error: 'danger',
  warning: 'warning',
  fatal: 'danger',
})
export const SANDBOX_STATUS = statusProxy('dictionary.sandboxStatus', ['online', 'offline'] as const, {
  online: 'success',
  offline: 'info',
})
export const REPORT_TYPE = labels('dictionary.reportType', [
  'problem',
  'solution',
  'post',
  'comment',
  'user',
] as const) as Record<ReportType, string>
export const configCategories = () =>
  ['site', 'auth_email', 'team', 'contest', 'sandbox', 'log', 'community'].map((value) => ({
    value,
    label: t(`dictionary.category.${value}`),
  }))
