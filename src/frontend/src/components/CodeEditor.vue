<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as monaco from 'monaco-editor'
import type { ProblemLanguage } from '@/api/types'

const props = defineProps<{ modelValue: string; language: ProblemLanguage }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const host = ref<HTMLElement>(); let editor: monaco.editor.IStandaloneCodeEditor | undefined
const monacoLanguage: Record<ProblemLanguage, string> = { cpp17: 'cpp', 'python3.12': 'python', java21: 'java' }
onMounted(() => { if (!host.value) return; editor = monaco.editor.create(host.value, { value: props.modelValue, language: monacoLanguage[props.language], theme: 'vs-dark', automaticLayout: true, minimap: { enabled: false }, fontSize: 14, tabSize: 4, scrollBeyondLastLine: false }); editor.onDidChangeModelContent(() => emit('update:modelValue', editor?.getValue() ?? '')) })
watch(() => props.language, value => monaco.editor.setModelLanguage(editor?.getModel()!, monacoLanguage[value]))
watch(() => props.modelValue, value => { if (editor && value !== editor.getValue()) editor.setValue(value) })
onBeforeUnmount(() => editor?.dispose())
</script>
<template><div ref="host" class="h-[560px] overflow-hidden rounded-lg border border-[var(--el-border-color)]" /></template>
