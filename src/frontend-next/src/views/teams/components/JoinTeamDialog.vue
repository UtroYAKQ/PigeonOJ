<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import { submitTeamApplication } from '@/api/teams'
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
import type { TeamSummary } from '@/types'

const props = defineProps<{
  open: boolean
  team: TeamSummary | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  applied: [teamId: string]
}>()

const { t } = useI18n()
const submitting = ref(false)

const content = computed(() => t('teams.list.applyConfirm', { name: props.team?.name ?? '' }))

function close(): void {
  if (submitting.value) return
  emit('update:open', false)
}

function onOpenChange(value: boolean): void {
  if (submitting.value) return
  emit('update:open', value)
}

async function confirm(): Promise<void> {
  if (!props.team || submitting.value) return
  submitting.value = true
  try {
    await submitTeamApplication(props.team.id)
    message.success(t('teams.list.applySuccess'))
    emit('applied', props.team.id)
    emit('update:open', false)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="onOpenChange">
    <DialogContent class="sm:max-w-[420px]">
      <DialogHeader>
        <DialogTitle>{{ t('teams.list.applyTitle') }}</DialogTitle>
        <DialogDescription>{{ content }}</DialogDescription>
      </DialogHeader>

      <DialogFooter>
        <Button variant="outline" size="sm" :disabled="submitting" @click="close">
          {{ t('action.cancel') }}
        </Button>
        <Button size="sm" :disabled="submitting" @click="confirm">
          <Loader2 v-if="submitting" class="size-3.5 animate-spin" />
          {{ t('teams.list.applyJoin') }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
