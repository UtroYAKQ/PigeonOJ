<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import { createReport } from '@/api/community'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { message } from '@/utils/feedback'
import type { ReportTargetType } from '@/types'

const props = defineProps<{
  open: boolean
  targetType: ReportTargetType
  targetId: string
}>()

const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const { t } = useI18n()
const reason = ref('')
const submitting = ref(false)

watch(
  () => props.open,
  (open) => {
    if (!open) return
    reason.value = ''
    submitting.value = false
  },
)

async function submit(): Promise<void> {
  const text = reason.value.trim()
  if (!text) {
    message.warning(t('community.report.reasonRequired'))
    return
  }
  submitting.value = true
  try {
    await createReport({
      target_type: props.targetType,
      target_id: props.targetId,
      reason: text,
    })
    message.success(t('community.report.success'))
    emit('update:open', false)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="emit('update:open', $event)">
    <DialogContent class="sm:max-w-[480px]">
      <DialogHeader>
        <DialogTitle>{{ t('community.report.title') }}</DialogTitle>
        <DialogDescription class="sr-only">{{ t('community.report.reasonRequired') }}</DialogDescription>
      </DialogHeader>
      <Textarea
        v-model="reason"
        rows="4"
        maxlength="2000"
        class="min-h-[100px] text-[13px]"
        :placeholder="t('community.report.placeholder')"
      />
      <DialogFooter>
        <Button
          variant="outline"
          size="sm"
          :disabled="submitting"
          @click="emit('update:open', false)"
        >
          {{ t('action.cancel') }}
        </Button>
        <Button size="sm" :disabled="submitting" @click="submit">
          <Loader2 v-if="submitting" class="size-4 animate-spin" />
          {{ t('community.report.submit') }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>