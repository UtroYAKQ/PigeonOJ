// 自定义 Monaco 主题：让编辑器与补全建议浮层贴合 PigeonOJ 设计系统。
// 配色硬编码对齐 src/frontend/src/assets/main.css 的 CSS 变量（Monaco 主题色无法引用 CSS 变量）。
// 注意：rules 中的 foreground 为 6 位 hex，不带 '#'；colors 中带 '#'。
import * as monaco from 'monaco-editor'

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
  'editor.background': '#ffffff',
  'editor.foreground': '#333639',
  'editorLineNumber.foreground': '#8a9099',
  'editorLineNumber.activeForeground': '#333639',
  'editorCursor.foreground': '#f4511e',
  'editor.selectionBackground': '#f4511e22',
  'editorIndentGuide.background': '#efeff5',
  'editorWhitespace.foreground': '#0000001a',
  'editorSuggestWidget.background': '#ffffff',
  'editorSuggestWidget.border': '#efeff5',
  'editorSuggestWidget.foreground': '#333639',
  'editorSuggestWidget.selectedBackground': '#f4511e1f',
  'editorSuggestWidget.selectedForeground': '#333639',
  'editorSuggestWidget.highlightForeground': '#f4511e',
  'editorSuggestWidgetStatus.background': '#fafafc',
  'editorHoverWidget.background': '#ffffff',
  'editorHoverWidget.border': '#efeff5',
  'editorWidget.background': '#ffffff',
  'editorWidget.border': '#efeff5',
  'focusBorder': '#f4511e',
}

const darkColors: Record<string, string> = {
  'editor.background': '#18181c',
  'editor.foreground': '#d2d2d6',
  'editorLineNumber.foreground': '#74747a',
  'editorLineNumber.activeForeground': '#d2d2d6',
  'editorCursor.foreground': '#f4511e',
  'editor.selectionBackground': '#f4511e33',
  'editorIndentGuide.background': '#ffffff14',
  'editorWhitespace.foreground': '#ffffff1a',
  'editorSuggestWidget.background': '#18181c',
  'editorSuggestWidget.border': '#2c2c30',
  'editorSuggestWidget.foreground': '#d2d2d6',
  'editorSuggestWidget.selectedBackground': '#f4511e33',
  'editorSuggestWidget.selectedForeground': '#d2d2d6',
  'editorSuggestWidget.highlightForeground': '#ff7a45',
  'editorSuggestWidgetStatus.background': '#202024',
  'editorHoverWidget.background': '#18181c',
  'editorHoverWidget.border': '#2c2c30',
  'editorWidget.background': '#18181c',
  'editorWidget.border': '#2c2c30',
  'focusBorder': '#f4511e',
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
