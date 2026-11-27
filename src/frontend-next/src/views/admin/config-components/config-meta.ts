/**
 * 系统配置编辑器元数据：编辑器类型判定 / 值摘要 / 下拉选项 / 列表隐藏键。
 * 由旧 AdminConfigsView（610 行单文件）拆分而来，保持后端契约与展示口径不变。
 */
import { i18n } from '@/i18n'
import type { SystemConfigItem } from '@/types'

export type ConfigEditorKind =
  'boolean' | 'banners' | 'image' | 'multiline' | 'number' | 'select' | 'switches' | 'text'

/** 首页轮播海报（site.banners，JSONB 数组，结构化编辑） */
export const BANNERS_KEY = 'site.banners'
/** 首页系统公告（site.announcement，Markdown 文本） */
export const ANNOUNCEMENT_KEY = 'site.announcement'
/** 站点 Logo（外链 URL 或 /files/upload/site-logo 返回的站内 URL） */
export const LOGO_KEY = 'site.logo'
/** 邮箱验证码 HTML 模板（多行 + 沙箱 iframe 预览） */
export const EMAIL_TEMPLATE_KEY = 'email.template.code_html'
/** 预览用示例验证码 */
export const EMAIL_PREVIEW_CODE = '123456'

/** 已废弃的配置键（后端仅向后兼容读取，管理界面不再展示，避免与 smtp_mode 混淆） */
const DEPRECATED_KEYS = new Set(['email.smtp.use_ssl'])

/** 首页专属配置：由「首页配置」（/admin/home）独立维护，不在系统配置列表重复展示 */
const HOME_CONFIG_KEYS = new Set([BANNERS_KEY, ANNOUNCEMENT_KEY])

/** 多行 / 富文本类配置键（用 textarea 编辑，避免单行输入框吞掉换行） */
const MULTILINE_KEYS = new Set([EMAIL_TEMPLATE_KEY, ANNOUNCEMENT_KEY])

type Translate = (key: string, params?: Record<string, unknown>) => string

/** 与 constants/dict.ts 同口径：非组件上下文按当前 locale 取词 */
const t: Translate = (key, params) =>
  (
    i18n as unknown as { global: { t: (k: string, p?: Record<string, unknown>) => string } }
  ).global.t(key, params)

export function isDeprecatedConfig(configKey: string): boolean {
  return DEPRECATED_KEYS.has(configKey)
}

/** 系统配置通用列表是否隐藏该键（已废弃 + 由独立页面维护的首页专属配置） */
export function isHiddenConfig(configKey: string): boolean {
  return isDeprecatedConfig(configKey) || HOME_CONFIG_KEYS.has(configKey)
}

/** 敏感配置（*.password，服务端掩码为 ******）用密码框编辑 */
export function isSecretConfig(configKey: string): boolean {
  return configKey.endsWith('.password')
}

/** 枚举型配置键的下拉选项（未收录的键返回空数组） */
export function selectOptionsFor(configKey: string): Array<{ label: string; value: string }> {
  if (configKey === 'site.default_theme') {
    return [
      { label: t('profile.light'), value: 'light' },
      { label: t('profile.dark'), value: 'dark' },
    ]
  }
  if (configKey === 'team.apply.review_rule') {
    return [
      { label: t('config.manualReview'), value: 'manual' },
      { label: t('config.autoApprove'), value: 'auto' },
    ]
  }
  if (configKey === 'email.smtp.smtp_mode') {
    return [
      { label: t('config.smtpMode.ssl'), value: 'ssl' },
      { label: t('config.smtpMode.starttls'), value: 'starttls' },
      { label: t('config.smtpMode.plain'), value: 'plain' },
    ]
  }
  return []
}

/** 依据配置键与值形态选择编辑器（海报 / Logo / 多行 / 布尔 / 数字 / 枚举 / 开关组 / 文本） */
export function resolveEditorKind(item: SystemConfigItem | null, value: unknown): ConfigEditorKind {
  if (!item) return 'text'
  if (MULTILINE_KEYS.has(item.config_key)) return 'multiline'
  if (item.config_key === BANNERS_KEY) return 'banners'
  if (item.config_key === LOGO_KEY) return 'image'
  if (typeof value === 'boolean') return 'boolean'
  if (typeof value === 'number') return 'number'
  if (selectOptionsFor(item.config_key).length > 0) return 'select'
  if (value && typeof value === 'object' && !Array.isArray(value)) return 'switches'
  return 'text'
}

/** 列表行的值摘要（不展开长文本；结构化配置只给规模 / 形态提示） */
export function describeConfigValue(item: SystemConfigItem): string {
  const value = item.config_value
  if (item.config_key === ANNOUNCEMENT_KEY) return t('config.announcementLabel')
  if (item.config_key === BANNERS_KEY) {
    return t('config.itemsCount', { count: Array.isArray(value) ? value.length : 0 })
  }
  if (MULTILINE_KEYS.has(item.config_key)) return t('config.htmlTemplateLabel')
  if (typeof value === 'boolean') return value ? t('config.booleanOn') : t('config.booleanOff')
  const options = selectOptionsFor(item.config_key)
  if (options.length > 0) {
    const hit = options.find((option) => option.value === String(value))
    if (hit) return hit.label
  }
  if (typeof value === 'string' && value.length > 60) return `${value.slice(0, 60)}…`
  if (value && typeof value === 'object') {
    if (Array.isArray(value)) return t('config.itemsCount', { count: value.length })
    return (
      Object.entries(value as Record<string, unknown>)
        .filter(([, enabled]) => enabled)
        .map(([key]) => key)
        .join(', ') || '—'
    )
  }
  return String(value ?? '—')
}

/** 邮箱验证码卡片预览：用示例值替换占位符（管理员自管内容，iframe sandbox 渲染） */
export function buildEmailPreview(raw: string): string {
  if (!raw.trim()) return ''
  return raw
    .replaceAll('{code}', EMAIL_PREVIEW_CODE)
    .replaceAll('{purpose}', t('config.previewPurpose'))
}
