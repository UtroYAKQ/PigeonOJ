import type { TagType } from '@/constants/dict'

/** 语义色唯一来源：徽标 / 文本 / 色块 / 提示条共用同一套 tone 映射 */
export type Tone = TagType | 'default' | 'error' | 'violet'

export const TONE_BADGE_CLASSES: Record<Tone, string> = {
  primary: 'border-brand/25 bg-brand-soft text-brand',
  success: 'border-emerald-600/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
  warning: 'border-amber-600/20 bg-amber-500/10 text-amber-700 dark:text-amber-400',
  danger: 'border-destructive/20 bg-destructive/10 text-destructive',
  error: 'border-destructive/20 bg-destructive/10 text-destructive',
  info: 'border-sky-600/20 bg-sky-500/10 text-sky-700 dark:text-sky-400',
  violet: 'border-violet-600/20 bg-violet-500/10 text-violet-700 dark:text-violet-400',
  default: 'border-border bg-muted text-muted-foreground',
}

/** 提示条：中性态用 surface 面，避免整块变灰底 */
export const TONE_NOTICE_CLASSES: Record<Tone, string> = {
  ...TONE_BADGE_CLASSES,
  default: 'border-border bg-surface text-muted-foreground',
}

export const TONE_DOT_CLASSES: Record<Tone, string> = {
  primary: 'bg-brand',
  success: 'bg-emerald-500',
  warning: 'bg-amber-500',
  danger: 'bg-destructive',
  error: 'bg-destructive',
  info: 'bg-sky-500',
  violet: 'bg-violet-500',
  default: 'bg-muted-foreground/50',
}

export const TONE_TEXT_CLASSES: Record<Tone, string> = {
  primary: 'text-brand',
  success: 'text-emerald-600 dark:text-emerald-400',
  warning: 'text-amber-600 dark:text-amber-400',
  danger: 'text-destructive',
  error: 'text-destructive',
  info: 'text-sky-600 dark:text-sky-400',
  violet: 'text-violet-600 dark:text-violet-400',
  default: 'text-muted-foreground',
}

/** 无描边的浅色块（看板格、状态摘要等） */
export const TONE_SURFACE_CLASSES: Record<Tone, string> = {
  primary: 'bg-brand-soft text-brand',
  success: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
  warning: 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
  danger: 'bg-destructive/10 text-destructive',
  error: 'bg-destructive/10 text-destructive',
  info: 'bg-sky-500/10 text-sky-700 dark:text-sky-400',
  violet: 'bg-violet-500/10 text-violet-700 dark:text-violet-400',
  default: 'bg-muted text-muted-foreground',
}

/** 实心色块（负载条等数据可视化） */
export const TONE_SOLID_CLASSES: Record<Tone, string> = {
  primary: 'bg-brand',
  success: 'bg-emerald-600',
  warning: 'bg-amber-500',
  danger: 'bg-destructive',
  error: 'bg-destructive',
  info: 'bg-sky-600',
  violet: 'bg-violet-600',
  default: 'bg-muted-foreground',
}