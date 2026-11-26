<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import { adminBanUser, adminFreezeUser } from '@/api/admin'
import DateTimeField from '@/components/common/DateTimeField.vue'
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
import { Textarea } from '@/components/ui/textarea'
import { message } from '@/utils/feedback'
import type { User } from '@/types'

const props = defineProps<{
  open: boolean
  action: 'ban' | 'freeze'
  user: User | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  done: []
}>()

const { t } = useI18n()
const reason = ref('')
const freezeUntil = ref<number | null>(null)
const submitting = ref(false)

const isFreeze = computed(() => props.action === 'freeze')
const actionLabel = computed(() =>
  isFreeze.value ? t('admin.users.freeze') : t('admin.users.ban'),
)

watch(
  () => props.open,
  (open) => {
    if (!open) return
    reason.value = ''
    freezeUntil.value = Date.now() + 15 * 60 * 1000
  },
)

function close(): void {
  emit('update:open', false)
}

async function submit(): Promise<void> {
  const user = props.user
  if (!user || submitting.value) return
  if (reason.value.length > 255) {
    message.warning(t('admin.users.reasonTooLong'))
    return
  }

  let durationMinutes: number | undefined
  if (isFreeze.value) {
    const until = freezeUntil.value
    if (until == null || Number.isNaN(until)) {
      message.warning(t('admin.users.freezeUntilInvalid'))
      return
    }
    durationMinutes = Math.round((until - Date.now()) / 60000)
    if (durationMinutes < 1 || durationMinutes > 7 * 24 * 60) {
      message.warning(t('admin.users.freezeUntilInvalid'))
      return
    }
  }

  submitting.value = true
  try {
    if (isFreeze.value) {
      await adminFreezeUser(user.id, reason.value, durationMinutes)
    } else {
      await adminBanUser(user.id, reason.value)
    }
    message.success(t('common.success'))
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
    <DialogContent class="sm:max-w-[460px]">
      <DialogHeader>
        <DialogTitle class="text-[15px] font-semibold">{{ actionLabel }}</DialogTitle>
        <DialogDescription>
          {{ t('admin.users.reasonPrompt', { action: actionLabel }) }}
        </DialogDescription>
      </DialogHeader>

      <form class="grid gap-3" @submit.prevent="submit">
        <div class="grid gap-1.5">
          <Textarea
            id="admin-user-reason"
            v-model="reason"
            rows="3"
            maxlength="255"
            class="min-h-[84px] text-[13px]"
            :aria-label="t('admin.users.reasonPrompt', { action: actionLabel })"
            :placeholder="isFreeze ? t('admin.users.freezeReason') : t('admin.users.banReason')"
          />
          <p class="text-right text-[11px] tabular-nums text-muted-foreground">
            {{ reason.length }}/255
          </p>
        </div>

        <div v-if="isFreeze" class="grid gap-1.5">
          <Label for="admin-user-freeze-until" class="text-[13px]">
            {{ t('admin.users.freezeUntil') }}
          </Label>
          <DateTimeField id="admin-user-freeze-until" v-model="freezeUntil" />
        </div>

        <p v-if="isFreeze" class="text-[12px] leading-5 text-muted-foreground">
          {{ t('admin.users.freezeHint') }}
        </p>
      </form>

      <DialogFooter>
        <Button variant="outline" size="sm" :disabled="submitting" @click="close">
          {{ t('action.cancel') }}
        </Button>
        <Button
          :variant="isFreeze ? 'default' : 'destructive'"
          size="sm"
          :disabled="submitting"
          @click="submit"
        >
          <Loader2 v-if="submitting" class="size-4 animate-spin" />
          {{ t('action.confirm') }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
