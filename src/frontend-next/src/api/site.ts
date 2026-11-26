/**
 * 站点公开信息 API（GET /site-config，未登录可读；docs/contracts/admin.md system_configs site 域）。
 */
import { apiRequest } from './http'
import type { SiteConfig } from '@/types'

/** GET /site-config — 公开站点配置（站点名 / Logo / ICP / 默认主题 / 注册开关） */
export function fetchSiteConfig() {
  return apiRequest<SiteConfig>('GET', '/site-config')
}
