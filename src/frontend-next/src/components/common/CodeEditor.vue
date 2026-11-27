<script setup lang="ts">
import { computed, nextTick, onActivated, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useMediaQuery, useResizeObserver } from '@vueuse/core'
import * as monaco from '@/monaco/setup'
import type { ProblemLanguage } from '@/types'
import { editorFontOption } from '@/constants/editorFonts'
import { registerProblemCompletions } from '@/monaco/completions'
import { definePigeonThemes, pigeonThemeName } from '@/monaco/theme'
import { useUserStore } from '@/stores/user'

const props = defineProps<{ modelValue: string; language: ProblemLanguage; readOnly?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const userStore = useUserStore()
const host = ref<HTMLElement>()
let editor: monaco.editor.IStandaloneCodeEditor | undefined
let themeObserver: MutationObserver | undefined

const monacoLanguage: Record<ProblemLanguage, string> = {
  cpp17: 'cpp',
  'python3.12': 'python',
  java21: 'java',
}

/** 窄屏自动换行，避免手机/平板上代码必须横向拖动 */
const isNarrow = useMediaQuery('(max-width: 640px)')
const fontOption = computed(() => editorFontOption(userStore.user?.editor_font_family))
const fontSize = computed(() => {
  const size = userStore.user?.editor_font_size ?? 14
  return Math.min(24, Math.max(11, size))
})

function currentTheme(): string {
  return pigeonThemeName(document.documentElement.classList.contains('dark'))
}

let resizeFrame: number | undefined

/** 合并同一帧内的多次重排请求，避免拖拽分栏 / 展开控制台时抖动 */
function relayout(): void {
  if (resizeFrame !== undefined) return
  resizeFrame = requestAnimationFrame(() => {
    resizeFrame = undefined
    editor?.layout()
  })
}

/** 显式等待字体就绪：否则 Monaco 会用回退字体的度量排版，逐字符累积宽度误差 */
async function ensureFontLoaded(fontFamily: string, fontSize: number): Promise<void> {
  const name = fontFamily.match(/['"]([^'"]+)['"]/)?.[1]
  if (!name) return
  try {
    await Promise.all([
      document.fonts.load(`${fontSize}px "${name}"`),
      document.fonts.load(`500 ${fontSize}px "${name}"`),
    ])
  } catch {
    /* 字体加载失败时按回退字体渲染 */
  }
}

/** 与旧 UI 一致：先等字体加载，再清 Monaco 度量缓存，最后应用新字体 */
async function applyFontPrefs(): Promise<void> {
  await ensureFontLoaded(fontOption.value.stack, fontSize.value)
  monaco.editor.remeasureFonts()
  editor?.updateOptions({
    fontSize: fontSize.value,
    fontFamily: fontOption.value.stack,
    fontLigatures: false,
  })
  relayout()
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
    // 控制台拖拽时容器高频重排，避免可见的横向滚动条被误触发
    scrollbar: { horizontal: 'hidden' },
    wordWrap: isNarrow.value ? 'on' : 'off',
    fontSize: fontSize.value,
    fontFamily: fontOption.value.stack,
    fontLigatures: false,
    tabSize: 4,
    scrollBeyondLastLine: false,
    readOnly: props.readOnly ?? false,
    // 行号区收窄：去掉 glyph margin 占位，行号最少 3 字符宽，行号与代码间距收到 4px
    glyphMargin: false,
    lineNumbersMinChars: 3,
    lineDecorationsWidth: 4,
  })
  editor.onDidChangeModelContent(() => emit('update:modelValue', editor?.getValue() ?? ''))
  themeObserver = new MutationObserver(() => {
    monaco.editor.setTheme(currentTheme())
  })
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
  // 首次挂载时父容器从 0 变为实际高度；字体加载完成后再测量一次
  relayout()
  void applyFontPrefs()
})

useResizeObserver(host, relayout)

onActivated(() => {
  // keep-alive 页面返回时容器尺寸可能已变化
  void nextTick().then(relayout)
})

watch(isNarrow, (narrow) => {
  editor?.updateOptions({ wordWrap: narrow ? 'on' : 'off' })
  relayout()
})

watch(
  () => [fontOption.value.value, fontSize.value] as const,
  () => {
    void applyFontPrefs()
  },
)
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
  <div
    ref="host"
    class="code-surface h-full min-h-0 w-full overflow-hidden rounded-lg border border-border"
  />
</template>
