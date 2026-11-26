import { h } from 'vue'
import { Check, Minus, X } from '@lucide/vue'

type Translate = (key: string) => string

/** 题库 / 题单列表共用的作答状态图标列：已通过 / 尝试未通过 / 未提交。 */
export function renderSolveMark(t: Translate, solved: boolean | null | undefined) {
  const mark =
    solved === true
      ? {
          icon: Check,
          class: 'text-emerald-600 dark:text-emerald-400',
          label: t('problems.list.solveSolved'),
        }
      : solved === false
        ? { icon: X, class: 'text-destructive', label: t('problems.list.solveAttempted') }
        : { icon: Minus, class: 'text-muted-foreground', label: t('problems.list.solveNever') }
  return h(mark.icon, {
    class: ['size-4', mark.class],
    'aria-label': mark.label,
  })
}
