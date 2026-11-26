<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import JSZip from 'jszip'

import { Button } from '@/components/ui/button'
import { message } from '@/utils/feedback'
import type { TestCaseDraft } from '@/types'

const emit = defineEmits<{ imported: [cases: TestCaseDraft[]] }>()
const { t } = useI18n()

const loading = ref(false)
const input = ref<HTMLInputElement>()
const MAX_ZIP = 20 * 1024 * 1024
const MAX_TOTAL = 100 * 1024 * 1024
const MAX_FILE = 2 * 1024 * 1024

type CasePair = { input?: string; output?: string }

/** 解析 ZIP 内的 {n}.in / {n}.out 配对文件并抛给宿主（校验解压体积与配对完整性） */
async function choose(event: Event): Promise<void> {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (file.size > MAX_ZIP) {
    message.error(t('problems.create.zipTooLarge'))
    return
  }
  loading.value = true
  try {
    const zip = await JSZip.loadAsync(file)
    const entries = new Map<number, CasePair>()
    let total = 0
    for (const [path, entry] of Object.entries(zip.files)) {
      if (entry.dir) continue
      const name = path.split('/').pop() ?? ''
      const match = /^(\d+)\.(in|out)$/.exec(name)
      if (!match) throw new Error(t('problems.create.zipInvalidName', { name }))
      const bytes = await entry.async('uint8array')
      total += bytes.byteLength
      if (bytes.byteLength > MAX_FILE || total > MAX_TOTAL) {
        throw new Error(t('problems.create.zipExpandedTooLarge'))
      }
      const number = Number(match[1])
      const item = entries.get(number) ?? {}
      item[match[2] === 'in' ? 'input' : 'output'] = new TextDecoder().decode(bytes)
      entries.set(number, item)
    }
    const cases: TestCaseDraft[] = [...entries.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([number, item], index) => {
        if (item.input === undefined || item.output === undefined) {
          throw new Error(t('problems.create.zipMissingPair', { name: number }))
        }
        return {
          name: String(number),
          input: item.input,
          expected_output: item.output,
          sort_order: index + 1,
        }
      })
    if (!cases.length) throw new Error(t('problems.create.zipEmpty'))
    emit('imported', cases)
    message.success(t('problems.create.zipImported', { count: cases.length }))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.create.zipInvalid'))
  } finally {
    loading.value = false
    if (input.value) input.value.value = ''
  }
}
</script>

<template>
  <Button variant="outline" size="sm" :disabled="loading" @click="input?.click()">
    <span
      v-if="loading"
      class="size-3.5 animate-spin rounded-full border border-current border-t-transparent"
    />
    {{ t('problems.create.importZip') }}
  </Button>
  <input ref="input" type="file" accept=".zip,application/zip" class="hidden" @change="choose" />
</template>
