<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
// Monaco 按需入口：仅编辑器核心 + cpp/python/java 高亮（见 src/monaco/setup.ts）
import * as monaco from '@/monaco/setup'
import type { ProblemLanguage } from '@/types'
import { registerProblemCompletions } from '@/monaco/completions'
import { definePigeonThemes, pigeonThemeName } from '@/monaco/theme'
import { editorFontStack, EDITOR_FONT_SIZES } from '@/constants/editorFonts'
import { useUserStore } from '@/stores/user'

const props = defineProps<{ modelValue: string; language: ProblemLanguage; readOnly?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const host = ref<HTMLElement>()
const userStore = useUserStore()

// 用户编辑器偏好（docs/contracts/users.md）：默认 JetBrains Mono / 14px，随个人资料即时变更
function editorPrefs() {
  const size = userStore.user?.editor_font_size ?? 14
  const { fontFamily, ligatures } = editorFontStack(userStore.user?.editor_font_family)
  return {
    fontSize: EDITOR_FONT_SIZES.includes(size) ? size : 14,
    fontFamily,
    fontLigatures: ligatures,
  }
}

/** 确保目标 web 字体已下载后再让 Monaco 测量：
 * 浏览器只在文本真正用到字体时才下载 woff2，若 Monaco 先用回退字体量宽、
 * 字体后到才替换渲染，光标坐标与字形就会错位（IBM Plex Mono 等首次使用时必现）。 */
async function ensureFontLoaded(fontSize: number) {
  const { webFont } = editorFontStack(userStore.user?.editor_font_family)
  if (!webFont) return // 系统等宽栈无 webfont，无需等待
  try {
    await Promise.all([
      document.fonts.load(`${fontSize}px "${webFont}"`),
      document.fonts.load(`500 ${fontSize}px "${webFont}"`),
    ])
  } catch {
    // 字体加载失败时仍应用字体栈（回退到系统等宽）
  }
}

async function applyFontPrefs() {
  const { fontSize, fontFamily, fontLigatures } = editorPrefs()
  await ensureFontLoaded(fontSize)
  // 关键：清空 Monaco 的字宽度量缓存——否则它继续用旧字体度量值排版，
  // 每输入一个字符光标就累积一份「度量宽 vs 渲染宽」的误差
  monaco.editor.remeasureFonts()
  editor?.updateOptions({ fontSize, fontFamily, fontLigatures })
}
let editor: monaco.editor.IStandaloneCodeEditor | undefined
let themeObserver: MutationObserver | undefined

const monacoLanguage: Record<ProblemLanguage, string> = {
  cpp17: 'cpp',
  'python3.12': 'python',
  java21: 'java',
}

// 编程字体：优先 JetBrains Mono（已通过 @fontsource 打包引入），回退系统等宽字体。
function currentTheme(): string {
  return pigeonThemeName(document.documentElement.classList.contains('dark'))
}

onMounted(() => {
  if (!host.value) return
  registerProblemCompletions()
  definePigeonThemes()
  editor = monaco.editor.create(host.value, {
    value: props.modelValue,
    language: monacoLanguage[props.language],
    theme: currentTheme(),
    automaticLayout: true,
    minimap: { enabled: false },
    ...editorPrefs(),
    tabSize: 4,
    scrollBeyondLastLine: false,
    // 不显示横向滚动条（超出部分仍可用 Shift+滚轮横向浏览）：自测控制台拖拽时
    // Monaco 自动布局随容器高度高频重排，可见的横向滚动条会被误触发出现
    scrollbar: { horizontal: 'hidden' },
    readOnly: props.readOnly ?? false,
  })
  editor.onDidChangeModelContent(() => emit('update:modelValue', editor?.getValue() ?? ''))
  // 字体下载完成后重测量一次，修正首次挂载时的光标/字形错位
  void applyFontPrefs()
  // 跟随全局主题（html.dark 由用户偏好驱动，见 assets/main.css）
  themeObserver = new MutationObserver(() => {
    monaco.editor.setTheme(currentTheme())
  })
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
})

watch(
  () => props.language,
  (value) => {
    const model = editor?.getModel()
    if (model) monaco.editor.setModelLanguage(model, monacoLanguage[value])
  },
)
watch(
  () => props.modelValue,
  (value) => {
    if (editor && value !== editor.getValue()) editor.setValue(value)
  },
)
// 字号 / 字体偏好变更：等字体就绪再应用，避免光标错位
watch(
  () => [userStore.user?.editor_font_size, userStore.user?.editor_font_family],
  () => {
    void applyFontPrefs()
  },
)
watch(
  () => props.readOnly,
  (value) => {
    editor?.updateOptions({ readOnly: value ?? false })
  },
)

onBeforeUnmount(() => {
  themeObserver?.disconnect()
  editor?.dispose()
})
</script>
<template>
  <div ref="host" class="code-editor" />
</template>

<style scoped>
/* 高度跟随父容器；父容器负责给定高度（详情页分栏内自适应，其他页面需显式设置） */
.code-editor {
  width: 100%;
  height: 100%;
  min-height: 220px;
  overflow: hidden;
  border-radius: var(--app-radius);
  border: 1px solid var(--app-border);
}

/* 文字区应用统一体系文本指针（main.css --app-cursor-text）：
 * 系统文本指针可能被设为白色，白底上不可见；整套黑色 I-Beam 保证编辑器内始终可辨。
 * 行号栏与其他控件保持各自光标。
 */
:deep(.monaco-editor),
:deep(.monaco-editor .view-lines),
:deep(.monaco-editor .view-overlays) {
  cursor: var(--app-cursor-text);
}
</style>
