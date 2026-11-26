<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Copy, Loader2 } from '@lucide/vue'

import { getVerifyInvite, initVerification } from '@/api/problems'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { copyToClipboard } from '@/utils/clipboard'
import { message } from '@/utils/feedback'

/** 邀请验题弹窗：先查现有有效链接，有则展示（可复制 / 重新生成），无则选择有效期生成 */
const props = defineProps<{
  open: boolean
  problemId: string
}>()

const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const { t } = useI18n()

const loading = ref(false)
const generating = ref(false)
const mode = ref<'generate' | 'view'>('generate')
const expiryHours = ref<24 | 72 | 168>(72)
const invite = ref<{ token: string; expires_at: string | null } | null>(null)

const inviteLink = computed(() =>
  invite.value ? `${window.location.origin}/verify/${invite.value.token}` : '',
)

const expiryOptions = computed(() => [
  { key: '24', label: t('problems.manage.expiry24'), hours: 24 as const },
  { key: '72', label: t('problems.manage.expiry72'), hours: 72 as const },
  { key: '168', label: t('problems.manage.expiry168'), hours: 168 as const },
])

watch(
  () => props.open,
  async (open) => {
    if (!open) return
    loading.value = true
    try {
      const existing = await getVerifyInvite(props.problemId)
      invite.value = existing
      mode.value = existing ? 'view' : 'generate'
    } catch {
      /* 查询失败回退到生成模式 */
      invite.value = null
      mode.value = 'generate'
    } finally {
      loading.value = false
    }
  },
)

async function generateInvite(hours: 24 | 72 | 168): Promise<void> {
  if (generating.value) return
  generating.value = true
  expiryHours.value = hours
  try {
    const result = await initVerification(props.problemId, { invite_expires_hours: hours })
    invite.value = result.invite ?? null
    mode.value = 'view'
    message.success(t('common.success'))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    generating.value = false
  }
}

async function copyLink(): Promise<void> {
  if (await copyToClipboard(inviteLink.value)) {
    message.success(t('problems.detail.copied'))
  } else {
    message.error(t('common.operationFailed'))
  }
}
</script>

<template>
  <Dialog :open="props.open" @update:open="emit('update:open', $event)">
    <DialogContent class="w-full max-w-[460px] gap-4">
      <DialogTitle class="text-[15px] font-semibold">
        {{ t('problems.manage.inviteDialogTitle') }}
      </DialogTitle>
      <DialogDescription class="sr-only">
        {{ t('problems.manage.inviteDialogTitle') }}
      </DialogDescription>

      <div v-if="loading" class="grid h-24 place-items-center">
        <Loader2 class="size-6 animate-spin text-muted-foreground" />
      </div>

      <div v-else-if="mode === 'view' && invite" class="space-y-3.5">
        <p class="text-[13px] leading-5 text-muted-foreground">
          {{ t('problems.manage.existingInvite') }}
        </p>
        <div class="flex items-center gap-2">
          <Input :model-value="inviteLink" readonly class="h-9 font-mono text-[12px]" />
          <Button variant="outline" size="toolbar" class="shrink-0" @click="copyLink">
            <Copy class="size-3.5" />
            {{ t('action.copyLink') }}
          </Button>
        </div>
        <div class="flex justify-end">
          <Button variant="outline" size="sm" :disabled="generating" @click="mode = 'generate'">
            {{ t('problems.manage.regenerate') }}
          </Button>
        </div>
      </div>

      <div v-else class="space-y-3.5">
        <p class="text-[13px] leading-5 text-muted-foreground">
          {{ t('problems.manage.expiryHint') }}
        </p>
        <div class="grid gap-2.5">
          <Button
            v-for="option in expiryOptions"
            :key="option.key"
            class="w-full"
            :variant="expiryHours === option.hours ? 'default' : 'outline'"
            :disabled="generating"
            @click="generateInvite(option.hours)"
          >
            <Loader2
              v-if="generating && expiryHours === option.hours"
              class="size-4 animate-spin"
            />
            {{ option.label }}
          </Button>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>
