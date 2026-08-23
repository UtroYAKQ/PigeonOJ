<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as monaco from 'monaco-editor'
import type { ProblemLanguage } from '@/types'

const props = defineProps<{ modelValue: string; language: ProblemLanguage; readOnly?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const host = ref<HTMLElement>()
let editor: monaco.editor.IStandaloneCodeEditor | undefined
let themeObserver: MutationObserver | undefined

const monacoLanguage: Record<ProblemLanguage, string> = { cpp17: 'cpp', 'python3.12': 'python', java21: 'java' }

function currentTheme(): string {
  return document.documentElement.classList.contains('dark') ? 'vs-dark' : 'vs'
}

onMounted(() => {
  if (!host.value) return
  editor = monaco.editor.create(host.value, {
    value: props.modelValue,
    language: monacoLanguage[props.language],
    theme: currentTheme(),
    automaticLayout: true,
    minimap: { enabled: false },
    fontSize: 14,
    tabSize: 4,
    scrollBeyondLastLine: false,
    readOnly: props.readOnly ?? false,
  })
  editor.onDidChangeModelContent(() => emit('update:modelValue', editor?.getValue() ?? ''))
  // 跟随全局主题（html.dark 由用户偏好驱动，见 assets/main.css）
  themeObserver = new MutationObserver(() => {
    monaco.editor.setTheme(currentTheme())
  })
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
})

watch(() => props.language, value => {
  const model = editor?.getModel()
  if (model) monaco.editor.setModelLanguage(model, monacoLanguage[value])
})
watch(() => props.modelValue, value => {
  if (editor && value !== editor.getValue()) editor.setValue(value)
})
watch(() => props.readOnly, value => {
  editor?.updateOptions({ readOnly: value ?? false })
})

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
  border-radius: 10px;
  border: 1px solid var(--app-border);
}
</style>
