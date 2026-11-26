/**
 * 代码编辑器字体偏好（docs/contracts/users.md）：
 * value 与后端 EditorFontFamily 白名单一致；stack 为 CSS 字体栈；
 * ligatures 标记该字体是否启用连字（Monaco fontLigatures）。
 */
export interface EditorFontOption {
  /** @fontsource 注册的 web 字体实名（system 栈无 webfont 为 null） */
  webFont: string | null
  value:
    | 'jetbrains-mono'
    | 'fira-code'
    | 'source-code-pro'
    | 'ibm-plex-mono'
    | 'cascadia-code'
    | 'system'
  label: string
  stack: string
  ligatures: boolean
}

export const EDITOR_FONT_OPTIONS: EditorFontOption[] = [
  {
    webFont: 'JetBrains Mono',
    value: 'jetbrains-mono',
    label: 'JetBrains Mono',
    stack:
      "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace",
    ligatures: true,
  },
  {
    webFont: 'Fira Code',
    value: 'fira-code',
    label: 'Fira Code',
    stack:
      "'Fira Code', ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace",
    ligatures: true,
  },
  {
    webFont: 'Cascadia Code',
    value: 'cascadia-code',
    label: 'Cascadia Code',
    stack:
      "'Cascadia Code', ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace",
    ligatures: true,
  },
  {
    webFont: 'Source Code Pro',
    value: 'source-code-pro',
    label: 'Source Code Pro',
    stack:
      "'Source Code Pro', ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace",
    ligatures: false,
  },
  {
    webFont: 'IBM Plex Mono',
    value: 'ibm-plex-mono',
    label: 'IBM Plex Mono',
    stack:
      "'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace",
    ligatures: false,
  },
  {
    webFont: null,
    value: 'system',
    label: '系统等宽',
    stack: "ui-monospace, 'Cascadia Mono', Consolas, Menlo, 'Courier New', monospace",
    ligatures: false,
  },
]

export const EDITOR_FONT_SIZES = [12, 13, 14, 15, 16, 17, 18, 20]

export function editorFontStack(value: string | undefined | null): {
  fontFamily: string
  ligatures: boolean
  webFont: string | null
} {
  const hit = EDITOR_FONT_OPTIONS.find((o) => o.value === value) ?? EDITOR_FONT_OPTIONS[0]
  return { fontFamily: hit.stack, ligatures: hit.ligatures, webFont: hit.webFont }
}

/** 应用启动时预载全部编辑器 web 字体：
 * 浏览器只在文本用到字体时才下载，若切换字体时才首次下载，Monaco 会先用回退字体
 * 量宽、字体后到才替换渲染——光标随输入逐字符漂移。预载消灭该竞态。 */
export async function preloadEditorFonts(): Promise<void> {
  const loads = EDITOR_FONT_OPTIONS.filter((o) => o.webFont).flatMap((o) => [
    document.fonts.load(`14px "${o.webFont}"`),
    document.fonts.load(`500 14px "${o.webFont}"`),
  ])
  await Promise.allSettled(loads)
}
