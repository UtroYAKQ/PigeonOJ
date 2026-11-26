<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import { adminHandleReport } from '@/api/admin'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { message } from '@/utils/feedback'
import type { Report } from '@/types'

const props = defineProps<{
  open: boolean
  report: Report | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  done: []
}>()

const { t } = useI18n()
const action = ref<'handled' | 'ignored'>('handled')
const submitting = ref(false)

const actions = [
  { value: 'handled', labelKey: 'admin.reports.approve' },
  { value: 'ignored', labelKey: 'admin.reports.ignore' },
] as const

const targetLabel = computed(() => {
  const report = props.report
  if (!report) return ''
  return report.target_summary ?? `#${report.target_id.slice(0, 8)}`
})

watch(
  () => props.open,
  (open) => {
    if (open) action.value = 'handled'
  },
)

function close(): void {
  emit('update:open', false)
}

async function submit(): Promise<void> {
  if (!props.report || submitting.value) return
  submitting.value = true
  try {
    await adminHandleReport(props.report.id, action.value)
    message.success(
      action.value === 'handled' ? t('admin.reports.handleSuccess') : t('admin.reports.ignored'),
    )
    close()
    emit('done')
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="sm:max-w-[440px]">
      <DialogHeader>
        <DialogTitle class="text-[15px] font-semibold">
          {{ t('admin.reports.handleTitle', { target: targetLabel }) }}
        </DialogTitle>
        <DialogDescription class="sr-only">{{ t('admin.reports.reason') }}</DialogDescription>
      </DialogHeader>

      <div class="grid gap-2" role="radiogroup" :aria-label="t('action.handle')">
        <label
          v-for="option in actions"
          :key="option.value"
          class="flex cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-2.5 text-[13px] transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring/50"
          :class="
            action === option.value
              ? 'border-foreground/25 bg-muted'
              : 'border-border hover:bg-muted/50'
          "
        >
          <input
            v-model="action"
            type="radio"
            name="report-handle-action"
            :value="option.value"
            class="sr-only"
          />
          <span
            class="grid size-3.5 shrink-0 place-items-center rounded-full border"
            :class="action === option.value ? 'border-foreground' : 'border-muted-foreground/50'"
          >
            <span v-if="action === option.value" class="size-1.5 rounded-full bg-foreground" />
          </span>
          <span>{{ t(option.labelKey) }}</span>
        </label>
      </div>

      <DialogFooter>
        <Button variant="outline" size="sm" :disabled="submitting" @click="close">
          {{ t('action.cancel') }}
        </Button>
        <Button size="sm" :disabled="submitting" @click="submit">
          <Loader2 v-if="submitting" class="size-4 animate-spin" />
          {{ t('action.confirm') }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
