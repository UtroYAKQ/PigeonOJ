<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, Loader2, Trash2 } from '@lucide/vue'

import { deleteCodeShare, getCodeShare } from '@/api/community'
import CommentThread from '@/components/community/CommentThread.vue'
import ReportDialog from '@/components/community/ReportDialog.vue'
import CodeBlockView from '@/components/common/CodeBlockView.vue'
import InlineNotice from '@/components/common/InlineNotice.vue'
import MarkdownView from '@/components/common/MarkdownView.vue'
import { Card } from '@/components/ui/card'
import PageShell from '@/components/common/PageShell.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import { Button } from '@/components/ui/button'
import { languageOptions } from '@/constants/languages'
import { useUserStore } from '@/stores/user'
import { confirmDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { CodeShareDetail } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const share = ref<CodeShareDetail | null>(null)
const loading = ref(false)

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
      <Card class="overflow-hidden">
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

          <CodeBlockView
            :code="share.code"
            :language="share.language"
            :title="languageLabel"
            max-height="max-h-[520px]"
          />
        </div>
      </Card>

      <div class="mt-4">
        <CommentThread target-type="code_share" :target-id="share.id" :disabled="removed" />
      </div>

      <ReportDialog v-model:open="reportOpen" target-type="code_share" :target-id="share.id" />
    </template>

    <Card v-else class="grid min-h-[320px] place-items-center">
      <p class="text-[13px] text-muted-foreground">{{ t('admin.codes.previewNotFound') }}</p>
    </Card>
  </PageShell>
</template>