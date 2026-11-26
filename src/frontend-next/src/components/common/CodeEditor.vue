<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
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

const fontOption = computed(() => editorFontOption(userStore.user?.editor_font_family))
const fontSize = computed(() => {
  const size = userStore.user?.editor_font_size ?? 14
  return Math.min(24, Math.max(11, size))
})

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
    fontSize: fontSize.value,
    fontFamily: fontOption.value.stack,
    fontLigatures: fontOption.value.ligatures,
    tabSize: 4,
    scrollBeyondLastLine: false,
    readOnly: props.readOnly ?? false,
    padding: { top: 10, bottom: 10 },
  })
  editor.onDidChangeModelContent(() => emit('update:modelValue', editor?.getValue() ?? ''))
  themeObserver = new MutationObserver(() => {
    monaco.editor.setTheme(currentTheme())
  })
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
})

watch(
  () => [fontOption.value.value, fontSize.value] as const,
  () => {
    editor?.updateOptions({
      fontSize: fontSize.value,
      fontFamily: fontOption.value.stack,
      fontLigatures: fontOption.value.ligatures,
    })
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
  <div ref="host" class="h-full min-h-0 w-full overflow-hidden rounded-lg border border-border" />
</template>
