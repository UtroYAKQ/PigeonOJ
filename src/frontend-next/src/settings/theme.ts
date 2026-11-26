/** 布局尺寸常量（新壳：顶栏 56px，侧栏展开 256px）。 */
export const LAYOUT = {
  siderWidth: 256,
  headerHeight: 56,
} as const

/** 小于该宽度时侧栏收为抽屉（与 PigeonAgent 参考一致）。 */
export const COLLAPSE_BREAKPOINT = 1024
