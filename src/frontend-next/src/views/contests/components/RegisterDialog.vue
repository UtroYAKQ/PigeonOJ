<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { formatDateTime } from '@/utils/format'
import type { ContestDetail } from '@/types'

const props = defineProps<{
  open: boolean
  detail: ContestDetail
  registering?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  confirm: []
}>()

const { t } = useI18n()

function onOpenChange(value: boolean): void {
  if (props.registering) return
  emit('update:open', value)
}
</script>

<template>
  <Dialog :open="open" @update:open="onOpenChange">
    <DialogContent class="sm:max-w-md">
      <DialogHeader>
        <DialogTitle>{{ t('contests.detail.register') }}</DialogTitle>
        <DialogDescription>{{ detail.title }}</DialogDescription>
      </DialogHeader>

      <dl class="grid grid-cols-2 gap-x-4 gap-y-3 text-[13px]">
        <div class="space-y-0.5">
          <dt class="text-[12px] text-muted-foreground">{{ t('contests.list.ruleType') }}</dt>
          <dd class="font-medium">{{ detail.rule_type }}</dd>
        </div>
        <div class="space-y-0.5">
          <dt class="text-[12px] text-muted-foreground">{{ t('contests.list.startTime') }}</dt>
          <dd class="font-medium tabular-nums">{{ formatDateTime(detail.start_time) }}</dd>
        </div>
        <div class="space-y-0.5">
          <dt class="text-[12px] text-muted-foreground">{{ t('contests.list.endTime') }}</dt>
          <dd class="font-medium tabular-nums">{{ formatDateTime(detail.end_time) }}</dd>
        </div>
        <div class="space-y-0.5">
          <dt class="text-[12px] text-muted-foreground">{{ t('contests.list.regStartTime') }}</dt>
          <dd class="font-medium tabular-nums">{{ formatDateTime(detail.register_start_time) }}</dd>
        </div>
        <div class="space-y-0.5">
          <dt class="text-[12px] text-muted-foreground">{{ t('contests.list.regEndTime') }}</dt>
          <dd class="font-medium tabular-nums">{{ formatDateTime(detail.register_end_time) }}</dd>
        </div>
      </dl>

      <DialogFooter>
        <Button variant="outline" :disabled="registering" @click="onOpenChange(false)">
          {{ t('action.cancel') }}
        </Button>
        <Button :disabled="registering" @click="emit('confirm')">
          <Loader2 v-if="registering" class="size-4 animate-spin" />
          {{ t('contests.detail.register') }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
