/**
 * site.logo 可渲染形态判断：
 * http(s) 外链，或站内文件 URL（POST /files/upload/site-logo 返回的 /api/v1/files/site/logo/…）。
 * 侧栏 Logo、favicon、管理端预览共用同一口径。
 */
export function isRenderableLogo(logo: string): boolean {
  return /^https?:\/\//.test(logo) || logo.startsWith('/api/v1/files/')
}
