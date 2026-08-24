import type { GlobalThemeOverrides } from 'naive-ui'

/**
 * 布局与主题参数（对齐 vue-fastapi-admin 视觉规范，见 docs/frontend.md）。
 * 主色取自参考模板 settings/theme.json 的 primaryColor。
 */
export const LAYOUT = {
  /** 侧栏展开宽度 */
  siderWidth: 220,
  /** 侧栏收起宽度（图标态） */
  siderCollapsedWidth: 64,
  /** 顶部栏高度 */
  headerHeight: 60,
  /** 内容画布底色（浅色 / 深色），同步定义于 assets/main.css 的 CSS 变量 */
  contentBgLight: '#f5f6fb',
  contentBgDark: '#101014',
} as const

/** 小于该宽度时侧栏强制收起（平板 / 移动端） */
export const COLLAPSE_BREAKPOINT = 991

export const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#F4511E',
    primaryColorHover: '#F4511E',
    primaryColorPressed: '#D84315',
    primaryColorSuppl: '#F4511E',
    infoColor: '#2080F0',
    successColor: '#18A058',
    warningColor: '#F0A020',
    errorColor: '#D03050',
    borderRadius: '3px',
  },
}
