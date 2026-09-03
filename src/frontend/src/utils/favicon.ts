/**
 * 浏览器标签图标：站点配置 site.logo 为外链 URL 或站内文件 URL 时用作 favicon，
 * 否则回退默认 🐦 图标（与侧栏 Logo 回退一致）。
 */
import { isRenderableLogo } from '@/utils/logo'

const DEFAULT_FAVICON =
  'data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🐦</text></svg>'

let lastApplied = ''

export function applyFavicon(logo: string): void {
  if (typeof document === 'undefined') return
  const href = isRenderableLogo(logo) ? logo : DEFAULT_FAVICON
  if (href === lastApplied) return
  let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
  if (!link) {
    link = document.createElement('link')
    link.rel = 'icon'
    document.head.appendChild(link)
  }
  link.href = href
  lastApplied = href
}
