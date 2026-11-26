<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, Check, Copy, Loader2, Trash2 } from '@lucide/vue'

import { deleteCodeShare, getCodeShare } from '@/api/community'
import CommentThread from '@/components/community/CommentThread.vue'
import ReportDialog from '@/components/community/ReportDialog.vue'
import InlineNotice from '@/components/common/InlineNotice.vue'
import MarkdownView from '@/components/common/MarkdownView.vue'
import PageShell from '@/components/common/PageShell.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import { Button } from '@/components/ui/button'
import { languageOptions } from '@/constants/languages'
import { TONE_TEXT_CLASSES } from '@/components/common/tone'
import { useUserStore } from '@/stores/user'
import { copyToClipboard } from '@/utils/clipboard'
import { confirmDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { CodeShareDetail } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const share = ref<CodeShareDetail | null>(null)
const loading = ref(false)
const copied = ref(false)
const reportOpen = ref(false)

const shareId = String(route.params.id)
const isOwner = computed(() => share.value?.author.id === userStore.user?.id)
const canManage = computed(() => isOwner.value || userStore.isAdmin)
const removed = computed(() => share.value?.status === 'removed')
const languageLabel = computed(() => {
  const value = share.value?.language
  return value ? (languageOptions.find((item) => item.value === value)?.label ?? value) : ''
})

async function load(): Promise<void> {
  loading.value = true
  try {
    share.value = await getCodeShare(shareId)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function copyCode(): Promise<void> {
  if (!share.value) return
  if (!(await copyToClipboard(share.value.code))) return
  copied.value = true
  message.success(t('problems.detail.copied'))
  window.setTimeout(() => (copied.value = false), 1500)
}

async function remove(): Promise<void> {
  const ok = await confirmDialog({
    title: t('codes.deleteTitle'),
    content: t('codes.deleteConfirm'),
    positiveText: t('codes.deleteTitle'),
    negativeText: t('action.cancel'),
    danger: true,
  })
  if (!ok) return
  try {
    await deleteCodeShare(shareId)
    message.success(t('common.success'))
    void router.push('/codes')
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

onMounted(load)
</script>

<template>
  <PageShell width="narrow">
    <template #actions>
      <Button variant="outline" size="sm" @click="router.push('/codes')">
        <ArrowLeft class="size-4" />
        {{ t('codes.backToList') }}
      </Button>
    </template>

    <div v-if="loading" class="grid min-h-[320px] place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <template v-else-if="share">
      <article class="overflow-hidden rounded-xl border border-border bg-card">
        <header class="border-b border-border px-5 py-4">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0">
              <h1 class="text-[20px] font-semibold leading-tight tracking-tight">
                {{ share.title }}
              </h1>
              <p class="mt-2 flex flex-wrap items-center gap-2 text-[12.5px] text-muted-foreground">
                <span>{{ share.author.nickname }}</span>
                <span aria-hidden="true">·</span>
                <span>{{ formatDateTime(share.updated_at) }}</span>
                <ToneBadge tone="info" :label="languageLabel" />
                <ToneBadge
                  v-if="removed"
                  tone="default"
                  :label="t('codes.statusRemoved')"
                />
              </p>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <Button v-if="userStore.isLoggedIn && !isOwner && !removed" variant="outline" size="sm" @click="reportOpen = true">
                {{ t('community.report.short') }}
              </Button>
              <Button v-if="canManage" variant="destructive" size="sm" @click="remove">
                <Trash2 class="size-4" />
                {{ t('codes.deleteTitle') }}
              </Button>
            </div>
          </div>
        </header>

        <div class="space-y-4 px-5 py-4">
          <InlineNotice v-if="removed" tone="warning">
            {{ t('codes.deleteConfirm') }}
          </InlineNotice>

          <MarkdownView v-if="share.description" :source="share.description" />

          <div class="overflow-hidden rounded-lg border border-border">
            <div class="flex items-center justify-between border-b border-border px-3 py-1.5">
              <span class="font-mono text-[12px] text-muted-foreground">{{ languageLabel }}</span>
              <Button
                variant="ghost"
                size="icon-xs"
                :aria-label="t('action.copy')"
                @click="copyCode"
              >
                <Check v-if="copied" class="size-3.5" :class="TONE_TEXT_CLASSES.success" />
                <Copy v-else class="size-3.5" />
              </Button>
            </div>
            <pre
              class="max-h-[520px] overflow-auto whitespace-pre-wrap break-all bg-code px-4 py-3 font-mono text-[12.5px] leading-6 text-code-foreground"
              >{{ share.code }}</pre
            >
          </div>
        </div>
      </article>

      <div class="mt-4">
        <CommentThread target-type="code_share" :target-id="share.id" :disabled="removed" />
      </div>

      <ReportDialog v-model:open="reportOpen" target-type="code_share" :target-id="share.id" />
    </template>

    <div v-else class="grid min-h-[320px] place-items-center rounded-xl border border-border bg-card">
      <p class="text-[13px] text-muted-foreground">{{ t('admin.codes.previewNotFound') }}</p>
    </div>
  </PageShell>
</template>