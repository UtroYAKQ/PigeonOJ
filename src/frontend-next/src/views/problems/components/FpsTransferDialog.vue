<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, Upload } from '@lucide/vue'

import { exportProblemXml, exportProblemsZip, importFpsProblems } from '@/api/problems'
import InlineNotice from '@/components/common/InlineNotice.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { TagType } from '@/constants/dict'
import { message } from '@/utils/feedback'
import type { FpsImportResult } from '@/types'

const props = defineProps<{
  open: boolean
  /** 列表勾选的题目 id（批量导出；跨页保留） */
  selectedIds: string[]
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  /** 导入成功且确有新题写入后通知宿主刷新列表 */
  imported: []
}>()

const { t } = useI18n()

const tab = ref<'import' | 'export'>('import')
const importing = ref(false)
const exporting = ref(false)
const importFile = ref<File | null>(null)
const importResult = ref<FpsImportResult | null>(null)
const importInput = ref<HTMLInputElement>()

const STATUS_TONES: Record<string, TagType> = {
  published: 'success',
  failed: 'danger',
  draft: 'warning',
  draft_spj: 'warning',
  duplicate: 'info',
  skipped_spj: 'info',
}

const summaryTone = computed(() =>
  importResult.value && importResult.value.imported > 0 ? 'success' : 'warning',
)

watch(
  () => props.open,
  (open) => {
    if (!open) return
    tab.value = 'import'
    importFile.value = null
    importResult.value = null
  },
)

function chooseImportFile(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!/\.(zip|xml|fps)$/i.test(file.name)) {
    message.error(t('problems.importFps.invalidType'))
    return
  }
  importFile.value = file
  importResult.value = null
}

async function doImport(): Promise<void> {
  if (!importFile.value || importing.value) return
  importing.value = true
  try {
    importResult.value = await importFpsProblems(importFile.value)
    if (importResult.value.imported > 0) emit('imported')
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.importFps.failed'))
  } finally {
    importing.value = false
  }
}

/** 批量导出 ZIP；单题 fps.xml 仅在恰好勾选 1 题时可用 */
async function doExport(kind: 'zip' | 'xml'): Promise<void> {
  if (exporting.value || !props.selectedIds.length) return
  if (kind === 'xml' && props.selectedIds.length !== 1) return
  exporting.value = true
  try {
    if (kind === 'zip') {
      await exportProblemsZip(props.selectedIds)
    } else {
      await exportProblemXml(props.selectedIds[0]!)
    }
    message.success(t('problems.importFps.exportSuccess'))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.importFps.failed'))
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <Dialog :open="props.open" @update:open="emit('update:open', $event)">
    <DialogContent class="max-h-[85vh] w-full max-w-[600px] gap-4 overflow-y-auto">
      <DialogHeader>
        <DialogTitle class="text-[15px] font-semibold">
          {{ t('problems.importFps.title') }}
        </DialogTitle>
        <DialogDescription class="sr-only">
          {{ t('problems.importFps.title') }}
        </DialogDescription>
      </DialogHeader>

      <Tabs v-model="tab" class="gap-3">
        <TabsList>
          <TabsTrigger value="import" class="px-3 text-[12px]">
            {{ t('problems.importFps.tabImport') }}
          </TabsTrigger>
          <TabsTrigger value="export" class="px-3 text-[12px]">
            {{ t('problems.importFps.tabExport') }}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="import" class="mt-0 grid gap-3">
          <p class="text-[12px] leading-6 text-muted-foreground">
            {{ t('problems.importFps.hint') }}
          </p>

          <div class="flex flex-wrap items-center gap-2.5">
            <input
              ref="importInput"
              type="file"
              accept=".zip,.xml,.fps"
              class="hidden"
              @change="chooseImportFile"
            />
            <Button variant="outline" size="sm" @click="importInput?.click()">
              <Upload class="size-4" />
              {{ t('problems.importFps.choose') }}
            </Button>
            <span v-if="importFile" class="min-w-0 flex-1 truncate text-[13px]">
              {{ importFile.name }}
            </span>
            <Button
              size="sm"
              class="ml-auto"
              :disabled="!importFile || importing"
              @click="doImport"
            >
              <Loader2 v-if="importing" class="size-4 animate-spin" />
              {{ t('problems.importFps.start') }}
            </Button>
          </div>

          <template v-if="importResult">
            <InlineNotice :tone="summaryTone">
              <p>
                {{
                  t('problems.importFps.summary', {
                    parsed: importResult.total_parsed,
                    imported: importResult.imported,
                  })
                }}
              </p>
              <p v-if="importResult.truncated">{{ t('problems.importFps.truncated') }}</p>
            </InlineNotice>

            <div
              v-if="importResult.results.length"
              class="grid max-h-[260px] gap-2 overflow-auto rounded-lg border border-border bg-muted/40 p-2.5"
            >
              <div
                v-for="(item, index) in importResult.results"
                :key="`${item.title}-${index}`"
                class="flex items-center gap-2 text-[12.5px]"
              >
                <ToneBadge
                  :tone="STATUS_TONES[item.status] ?? 'info'"
                  :label="t(`problems.importFps.status_${item.status}`)"
                />
                <span class="min-w-0 flex-1 truncate">{{ item.title }}</span>
                <span
                  v-if="item.message"
                  class="max-w-[45%] truncate text-[12px] text-muted-foreground"
                  :title="item.message"
                >
                  {{ item.message }}
                </span>
              </div>
            </div>
          </template>
        </TabsContent>

        <TabsContent value="export" class="mt-0 grid gap-3">
          <p class="text-[12px] leading-6 text-muted-foreground">
            {{ t('problems.importFps.exportHint') }}
          </p>

          <div
            v-if="!props.selectedIds.length"
            class="rounded-lg border border-border bg-muted/40 px-3 py-2 text-[12.5px] text-muted-foreground"
          >
            {{ t('problems.importFps.exportNone') }}
          </div>

          <template v-else>
            <p class="text-[13px]">
              {{ t('problems.importFps.selectedCount', { count: props.selectedIds.length }) }}
            </p>
            <div class="flex justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                :disabled="props.selectedIds.length !== 1 || exporting"
                @click="doExport('xml')"
              >
                {{ t('problems.importFps.exportXml') }}
              </Button>
              <Button size="sm" :disabled="exporting" @click="doExport('zip')">
                <Loader2 v-if="exporting" class="size-4 animate-spin" />
                {{ t('problems.importFps.exportZip') }}
              </Button>
            </div>
          </template>
        </TabsContent>
      </Tabs>
    </DialogContent>
  </Dialog>
</template>
