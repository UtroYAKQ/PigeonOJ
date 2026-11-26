// 自定义 Monaco 主题：让编辑器与补全建议浮层贴合 PigeonOJ 设计系统。
// 配色硬编码对齐 src/frontend-next/src/assets/main.css 的 CSS 变量（Monaco 主题色无法引用 CSS 变量）。
// 注意：rules 中的 foreground 为 6 位 hex，不带 '#'；colors 中带 '#'。
import * as monaco from '@/monaco/setup'

export const PIGEON_LIGHT = 'pigeon-light'
export const PIGEON_DARK = 'pigeon-dark'

// 语法着色（GitHub Light / GitHub Dark 风格，等宽编程字体下观感清爽）
const lightRules: monaco.editor.ITokenThemeRule[] = [
  { token: '', foreground: '24292f' },
  { token: 'comment', foreground: '6e7781', fontStyle: 'italic' },
  { token: 'string', foreground: '0a3069' },
  { token: 'string.escape', foreground: '0550ae' },
  { token: 'number', foreground: '0550ae' },
  { token: 'constant.numeric', foreground: '0550ae' },
  { token: 'constant.language', foreground: '0550ae' },
  { token: 'keyword', foreground: 'cf222e' },
  { token: 'keyword.control', foreground: 'cf222e' },
  { token: 'storage.type', foreground: '953800' },
  { token: 'entity.name.type', foreground: '953800' },
  { token: 'entity.name.class', foreground: '953800' },
  { token: 'entity.name.function', foreground: '8250df' },
  { token: 'support.function', foreground: '8250df' },
  { token: 'support.type', foreground: '953800' },
  { token: 'meta.preprocessor', foreground: '8250df' },
  { token: 'variable', foreground: '24292f' },
]

const darkRules: monaco.editor.ITokenThemeRule[] = [
  { token: '', foreground: 'c9d1d9' },
  { token: 'comment', foreground: '8b949e', fontStyle: 'italic' },
  { token: 'string', foreground: 'a5d6ff' },
  { token: 'string.escape', foreground: '79c0ff' },
  { token: 'number', foreground: '79c0ff' },
  { token: 'constant.numeric', foreground: '79c0ff' },
  { token: 'constant.language', foreground: '79c0ff' },
  { token: 'keyword', foreground: 'ff7b72' },
  { token: 'keyword.control', foreground: 'ff7b72' },
  { token: 'storage.type', foreground: 'ffa657' },
  { token: 'entity.name.type', foreground: 'ffa657' },
  { token: 'entity.name.class', foreground: 'ffa657' },
  { token: 'entity.name.function', foreground: 'd2a8ff' },
  { token: 'support.function', foreground: 'd2a8ff' },
  { token: 'support.type', foreground: 'ffa657' },
  { token: 'meta.preprocessor', foreground: 'd2a8ff' },
  { token: 'variable', foreground: 'c9d1d9' },
]

const lightColors: Record<string, string> = {
  'editor.background': '#fafafa',
  'editor.foreground': '#1a1a1a',
  'editorLineNumber.foreground': '#9a9aa3',
  'editorLineNumber.activeForeground': '#1a1a1a',
  'editorCursor.foreground': '#d9480f',
  'editor.selectionBackground': '#d9480f26',
  'editorIndentGuide.background': '#ececee',
  'editorWhitespace.foreground': '#0000001a',
  'editorSuggestWidget.background': '#ffffff',
  'editorSuggestWidget.border': '#e5e5e5',
  'editorSuggestWidget.foreground': '#1a1a1a',
  // 选中底加深（12% → 18%）：淡底上选中态不明显
  'editorSuggestWidget.selectedBackground': '#d9480f24',
  'editorSuggestWidget.selectedForeground': '#1a1a1a',
  // 匹配字符高亮用主色 pressed（#f4511e 白底对比仅 3.5:1，偏浅看不清）；
  // focusHighlightForeground 为聚焦行（当前选中项）匹配高亮，未覆盖时继承
  // vs 基础主题的浅青蓝默认值（0.52+ 拆分键），须一并覆盖
  'editorSuggestWidget.highlightForeground': '#c2410c',
  'editorSuggestWidget.focusHighlightForeground': '#c2410c',
  'editorSuggestWidgetStatus.background': '#f7f7f8',
  'editorHoverWidget.background': '#ffffff',
  'editorHoverWidget.border': '#e5e5e5',
  'editorWidget.background': '#ffffff',
  'editorWidget.border': '#e5e5e5',
  focusBorder: '#d9480f',
}

const darkColors: Record<string, string> = {
  'editor.background': '#1b1b1b',
  'editor.foreground': '#e8e8e8',
  'editorLineNumber.foreground': '#7a7a85',
  'editorLineNumber.activeForeground': '#e8e8e8',
  'editorCursor.foreground': '#d9480f',
  'editor.selectionBackground': '#f08a5d33',
  'editorIndentGuide.background': '#ffffff12',
  'editorWhitespace.foreground': '#ffffff1a',
  'editorSuggestWidget.background': '#2f2f2f',
  'editorSuggestWidget.border': '#3a3a3a',
  'editorSuggestWidget.foreground': '#e8e8e8',
  'editorSuggestWidget.selectedBackground': '#f08a5d33',
  'editorSuggestWidget.selectedForeground': '#e8e8e8',
  // GitHub dark 橙：暗底上比 #ff7a45 更亮更醒目；聚焦行匹配高亮同源（默认浅青蓝）
  'editorSuggestWidget.highlightForeground': '#ffa657',
  'editorSuggestWidget.focusHighlightForeground': '#ffa657',
  'editorSuggestWidgetStatus.background': '#2a2a2a',
  'editorHoverWidget.background': '#2f2f2f',
  'editorHoverWidget.border': '#3a3a3a',
  'editorWidget.background': '#2f2f2f',
  'editorWidget.border': '#3a3a3a',
  focusBorder: '#d9480f',
}

let defined = false

// 定义一次即可（模块级守卫避免 dev HMR 重复定义告警）
export function definePigeonThemes(): void {
  if (defined) return
  defined = true
  monaco.editor.defineTheme(PIGEON_LIGHT, {
    base: 'vs',
    inherit: true,
    rules: lightRules,
    colors: lightColors,
  })
  monaco.editor.defineTheme(PIGEON_DARK, {
    base: 'vs-dark',
    inherit: true,
    rules: darkRules,
    colors: darkColors,
  })
}

export function pigeonThemeName(dark: boolean): string {
  return dark ? PIGEON_DARK : PIGEON_LIGHT
}
