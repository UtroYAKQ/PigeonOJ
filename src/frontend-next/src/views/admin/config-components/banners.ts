/**
 * 首页轮播海报草稿工具：site.banners 的加载归一化与保存归一化。
 * 后台「首页配置」与「系统配置 · 站点域」共用同一口径。
 */
import type { SiteBanner } from '@/types'

/** 编辑态草稿（允许空图片的半成品行，保存时过滤） */
export interface BannerDraft {
  image: string
  title: string
  link: string
}

export const MAX_BANNERS = 10

function asDraft(item: unknown): BannerDraft {
  const row = (item ?? {}) as Partial<SiteBanner>
  return {
    image: String(row.image ?? ''),
    title: String(row.title ?? ''),
    link: String(row.link ?? ''),
  }
}

/** 配置值 → 草稿数组（容忍非数组 / 脏字段） */
export function toBannerDraft(value: unknown): BannerDraft[] {
  return Array.isArray(value) ? value.map(asDraft) : []
}

/** 草稿 → 契约三元组：无图片的半成品条目自动丢弃，字段去首尾空白 */
export function normalizeBanners(list: BannerDraft[]): SiteBanner[] {
  return list
    .filter((banner) => banner.image.trim())
    .map((banner) => ({
      image: banner.image.trim(),
      title: banner.title.trim(),
      link: banner.link.trim(),
    }))
}
