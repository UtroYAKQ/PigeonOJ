/**
 * 浏览器标签图标：站点配置 site.logo 为外链 URL 或站内文件 URL 时用作 favicon，
 * 否则回退默认站点 Logo（与侧栏品牌标识一致）。
 */
import { isRenderableLogo } from '@/utils/logo'

const DEFAULT_FAVICON = '/brand/favicon.png'

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
