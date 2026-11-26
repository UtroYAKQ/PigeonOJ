<script setup lang="ts">
/**
 * 异常日志堆栈详情弹窗：消息 / request_id / traceback（等宽滚动区）。
 */
import { useI18n } from 'vue-i18n'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { ExceptionLogRow } from '@/types'

defineProps<{ row: ExceptionLogRow | null }>()

const open = defineModel<boolean>('open', { default: false })
const { t } = useI18n()
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent class="max-h-[82vh] overflow-hidden sm:max-w-[820px]">
      <DialogHeader>
        <DialogTitle class="text-[15px]">{{ t('admin.logs.tracebackTitle') }}</DialogTitle>
        <DialogDescription class="sr-only">
          {{ t('admin.logs.tracebackTitle') }}
        </DialogDescription>
      </DialogHeader>

      <div v-if="row" class="min-w-0 space-y-2.5">
        <p class="text-[13px] font-medium break-words">{{ row.message }}</p>
        <p v-if="row.request_id" class="font-mono text-[11.5px] text-muted-foreground">
          {{ t('admin.logs.requestId') }}: {{ row.request_id }}
        </p>
        <pre
          v-if="row.traceback"
          class="max-h-[52vh] overflow-auto rounded-lg border border-border bg-code p-3 font-mono text-[12px] leading-5 break-all whitespace-pre-wrap text-code-foreground"
          >{{ row.traceback }}</pre>
        <p v-else class="text-[13px] text-muted-foreground">{{ t('admin.logs.noTraceback') }}</p>
      </div>
    </DialogContent>
  </Dialog>
</template>
