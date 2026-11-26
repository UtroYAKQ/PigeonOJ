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
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
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

const actionModel = computed({
  get: () => action.value,
  set: (value: string) => {
    action.value = value as 'handled' | 'ignored'
  },
})

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

      <RadioGroup v-model="actionModel" class="grid gap-2" :aria-label="t('action.handle')">
        <Label
          v-for="option in actions"
          :key="option.value"
          class="flex cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-2.5 text-[13px] transition-colors"
          :class="
            action === option.value
              ? 'border-foreground/25 bg-muted'
              : 'border-border hover:bg-muted/50'
          "
        >
          <RadioGroupItem :value="option.value" />
          <span>{{ t(option.labelKey) }}</span>
        </Label>
      </RadioGroup>

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
