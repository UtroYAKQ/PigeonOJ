<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Copy, Loader2, RefreshCw } from '@lucide/vue'
import QRCode from 'qrcode'

import { createTeamInvite } from '@/api/teams'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { copyToClipboard } from '@/utils/clipboard'
import { message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'

/** 团队邀请链接弹窗：打开即生成，展示二维码 / 链接 / 有效期（链接多人可用） */
const props = defineProps<{
  open: boolean
  teamId: string
}>()

const emit = defineEmits<{ 'update:open': [value: boolean] }>()

const { t } = useI18n()

const token = ref('')
const expiresAt = ref('')
const expiresAtRaw = ref('')
const loading = ref(false)
const qrDataUrl = ref('')

const inviteLink = computed(() =>
  token.value ? `${window.location.origin}/teams/invites/${token.value}` : '',
)

function canReuse(): boolean {
  if (!token.value || !expiresAtRaw.value) return false
  return new Date(expiresAtRaw.value).getTime() > Date.now()
}

async function renderQr(): Promise<void> {
  if (!inviteLink.value) return
  qrDataUrl.value = await QRCode.toDataURL(inviteLink.value, {
    width: 220,
    margin: 1,
    errorCorrectionLevel: 'M',
  })
}

async function generate(): Promise<void> {
  if (loading.value) return
  loading.value = true
  try {
    const result = await createTeamInvite(props.teamId)
    token.value = result.token
    expiresAt.value = formatDateTime(result.expires_at)
    expiresAtRaw.value = result.expires_at
    await renderQr()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    loading.value = false
  }
}

watch(
  () => props.open,
  (open) => {
    if (!open) return
    if (canReuse()) {
      if (!qrDataUrl.value) void renderQr()
      return
    }
    void generate()
  },
)

async function copyInviteLink(): Promise<void> {
  const ok = await copyToClipboard(inviteLink.value)
  if (ok) message.success(t('common.copied'))
  else message.error(t('common.copyFailed'))
}
</script>

<template>
  <Dialog :open="props.open" @update:open="emit('update:open', $event)">
    <DialogContent class="w-full max-w-[420px] gap-4">
      <DialogTitle class="text-[15px] font-semibold">
        {{ t('teams.settings.inviteTitle') }}
      </DialogTitle>
      <DialogDescription class="text-[12.5px] leading-5">
        {{ t('teams.settings.inviteHint') }}
      </DialogDescription>

      <div v-if="loading" class="grid h-40 place-items-center">
        <Loader2 class="size-5 animate-spin text-muted-foreground" />
      </div>

      <div v-else-if="token" class="space-y-3.5">
        <div class="flex justify-center">
          <img
            v-if="qrDataUrl"
            :src="qrDataUrl"
            :alt="t('teams.settings.inviteTitle')"
            class="size-[200px] rounded-md border border-border bg-white p-2"
          />
        </div>
        <div class="flex items-center gap-2">
          <Input
            :model-value="inviteLink"
            readonly
            class="h-9 font-mono text-[12px]"
            @focus="($event.target as HTMLInputElement).select()"
          />
          <Button variant="outline" size="toolbar" class="shrink-0" @click="copyInviteLink">
            <Copy class="size-3.5" />
            {{ t('action.copyLink') }}
          </Button>
        </div>
        <div
          class="flex flex-wrap items-center justify-between gap-2 text-[11.5px] tabular-nums text-muted-foreground"
        >
          <span>{{ t('teams.settings.inviteExpiry', { time: expiresAt }) }}</span>
          <Button variant="ghost" size="xs" :disabled="loading" @click="generate">
            <RefreshCw class="size-3.5" />
            {{ t('teams.settings.regenerate') }}
          </Button>
        </div>
      </div>

      <div v-else class="space-y-3">
        <p class="text-[13px] text-muted-foreground">{{ t('common.operationFailed') }}</p>
        <Button class="w-full" @click="generate">
          {{ t('teams.settings.generateInvite') }}
        </Button>
      </div>
    </DialogContent>
  </Dialog>
</template>