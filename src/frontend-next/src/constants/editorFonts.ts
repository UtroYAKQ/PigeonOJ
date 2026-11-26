/**
 * 代码编辑器字体偏好（docs/contracts/users.md）：
 * value 与后端白名单一致；stack 为 CSS 字体栈；ligatures 控制 Monaco 连字。
 * 仅 JetBrains Mono 随应用打包，其余字体使用系统已安装版本，未安装时回退等宽字体。
 */
export type EditorFontValue =
  | 'jetbrains-mono'
  | 'fira-code'
  | 'source-code-pro'
  | 'ibm-plex-mono'
  | 'cascadia-code'
  | 'system'

export interface EditorFontOption {
  value: EditorFontValue
  label: string
  stack: string
  ligatures: boolean
}

export const EDITOR_FONT_OPTIONS: EditorFontOption[] = [
  {
    value: 'jetbrains-mono',
    label: 'JetBrains Mono',
    stack:
      "'JetBrains Mono', 'Geist Mono Variable', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
    ligatures: true,
  },
  {
    value: 'fira-code',
    label: 'Fira Code',
    stack:
      "'Fira Code', 'Geist Mono Variable', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
    ligatures: true,
  },
  {
    value: 'cascadia-code',
    label: 'Cascadia Code',
    stack:
      "'Cascadia Code', 'Geist Mono Variable', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
    ligatures: true,
  },
  {
    value: 'source-code-pro',
    label: 'Source Code Pro',
    stack:
      "'Source Code Pro', 'Geist Mono Variable', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
    ligatures: false,
  },
  {
    value: 'ibm-plex-mono',
    label: 'IBM Plex Mono',
    stack:
      "'IBM Plex Mono', 'Geist Mono Variable', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
    ligatures: false,
  },
  {
    value: 'system',
    label: '系统等宽',
    stack: "ui-monospace, 'Cascadia Mono', Consolas, Menlo, 'Courier New', monospace",
    ligatures: false,
  },
]

export const EDITOR_FONT_SIZES = [12, 13, 14, 15, 16, 17, 18, 20]

export function editorFontOption(value: string | null | undefined): EditorFontOption {
  return EDITOR_FONT_OPTIONS.find((option) => option.value === value) ?? EDITOR_FONT_OPTIONS[0]!
}