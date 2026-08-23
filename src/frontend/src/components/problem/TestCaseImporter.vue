<script setup lang="ts">
import JSZip from 'jszip'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import type { TestCaseDraft } from '@/types'

const emit = defineEmits<{ imported: [cases: TestCaseDraft[]] }>()
const { t } = useI18n(); const loading = ref(false); const input = ref<HTMLInputElement>()
const MAX_ZIP = 20 * 1024 * 1024; const MAX_TOTAL = 100 * 1024 * 1024; const MAX_FILE = 2 * 1024 * 1024
async function choose(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]; if (!file) return
  if (file.size > MAX_ZIP) { ElMessage.error(t('problems.create.zipTooLarge')); return }
  loading.value = true
  try {
    const zip = await JSZip.loadAsync(file); const entries = new Map<number, { input?: string; output?: string }>(); let total = 0
    for (const [path, entry] of Object.entries(zip.files)) {
      if (entry.dir) continue
      const name = path.split('/').pop() ?? ''; const match = /^(\d+)\.(in|out)$/.exec(name)
      if (!match) throw new Error(t('problems.create.zipInvalidName', { name }))
      const bytes = await entry.async('uint8array'); total += bytes.byteLength
      if (bytes.byteLength > MAX_FILE || total > MAX_TOTAL) throw new Error(t('problems.create.zipExpandedTooLarge'))
      const text = new TextDecoder().decode(bytes); const number = Number(match[1]); const item = entries.get(number) ?? {}; item[match[2] === 'in' ? 'input' : 'output'] = text; entries.set(number, item)
    }
    const cases: TestCaseDraft[] = [...entries.entries()].sort((a, b) => a[0] - b[0]).map(([number, item], index) => { if (item.input === undefined || item.output === undefined) throw new Error(t('problems.create.zipMissingPair', { name: number })); return { name: String(number), input: item.input, expected_output: item.output, is_sample: false, score: 0, sort_order: index + 1 } })
    if (!cases.length) throw new Error(t('problems.create.zipEmpty'))
    emit('imported', cases); ElMessage.success(t('problems.create.zipImported', { count: cases.length }))
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : t('problems.create.zipInvalid')) } finally { loading.value = false; if (input.value) input.value.value = '' }
}
</script>
<template><el-button :loading="loading" @click="input?.click()">{{ t('problems.create.importZip') }}</el-button><input ref="input" type="file" accept=".zip,application/zip" hidden @change="choose"></template>
