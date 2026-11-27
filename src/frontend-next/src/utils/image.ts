/**
 * 站内图片缩略地址。
 *
 * 后端 `GET /api/v1/files/{key}?w=` 只接受固定宽度档位
 * （见 `app/services/file.py` 的 THUMB_WIDTHS），按档返回 WebP 缩略图；
 * 这里按目标展示宽度就近向上取档，外链 / 已带 query 的地址原样返回。
 */
const SITE_FILE_PREFIX = '/api/v1/files/'

export const THUMB_WIDTHS = [96, 192, 384, 640, 960, 1280] as const

export function siteImageUrl(url: string | null | undefined, targetWidth: number): string {
  if (!url) return ''
  if (!url.startsWith(SITE_FILE_PREFIX)) return url
  if (url.includes('?')) return url
  const width = THUMB_WIDTHS.find((item) => item >= targetWidth)
    ?? THUMB_WIDTHS[THUMB_WIDTHS.length - 1]
  return `${url}?w=${width}`
}

/** 头像按 2x 像素取档（Retina 下也清晰），最小 96 档 */
export function avatarImageUrl(url: string | null | undefined, displaySize: number): string {
  return siteImageUrl(url, Math.max(96, Math.round(displaySize * 2)))
}