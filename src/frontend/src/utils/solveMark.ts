import { h } from 'vue'
import { NIcon } from 'naive-ui'
import { Check, Close, Minus } from '@element-plus/icons-vue'

type Translate = (key: string) => string

/**
 * 题库 / 题单列表共用的作答状态图标列渲染：
 * 已通过（绿 Check）/ 已尝试未通过（红 Close）/ 未提交过（灰 Minus）。
 * 颜色经 NIcon color prop 直填——h() 渲染函数生成的 DOM 不带 scoped 属性，scoped CSS 够不着。
 */
export function renderSolveMark(t: Translate, solved: boolean | null | undefined) {
  const mark =
    solved === true
      ? { icon: Check, color: 'var(--app-success)', label: t('problems.list.solveSolved') }
      : solved === false
        ? { icon: Close, color: 'var(--app-error)', label: t('problems.list.solveAttempted') }
        : { icon: Minus, color: 'var(--app-text-secondary)', label: t('problems.list.solveNever') }
  return h(NIcon, {
    component: mark.icon,
    color: mark.color,
    size: 16,
    title: mark.label,
    'aria-label': mark.label,
  })
}
