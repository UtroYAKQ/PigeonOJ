<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { FileQuestion, Loader2, PenLine, Trash2 } from '@lucide/vue'

import { deleteCodeShare, getCodeShare } from '@/api/community'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import CodeBlockView from '@/components/common/CodeBlockView.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import InlineNotice from '@/components/common/InlineNotice.vue'
import MarkdownView from '@/components/common/MarkdownView.vue'
import PageShell from '@/components/common/PageShell.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import CommentThread from '@/components/community/CommentThread.vue'
import ReportDialog from '@/components/community/ReportDialog.vue'
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
  <PageShell>
    <div v-if="loading" class="list-empty">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <template v-else-if="share">
      <div class="space-y-8">
        <header class="flex flex-wrap items-start justify-between gap-3">
          <div class="flex min-w-0 items-start gap-3">
            <BaseAvatar
              kind="user"
              :src="share.author.avatar_url"
              :name="share.author.nickname"
              :size="40"
              class="mt-0.5"
            />
            <div class="min-w-0">
              <h1 class="text-[20px] font-semibold leading-tight tracking-tight">
                {{ share.title }}
              </h1>
              <p class="mt-2 flex flex-wrap items-center gap-2 text-[12.5px] text-muted-foreground">
                <span>{{ share.author.nickname }}</span>
                <span aria-hidden="true">·</span>
                <span>{{ formatDateTime(share.updated_at) }}</span>
                <ToneBadge tone="info" :label="languageLabel" />
                <ToneBadge v-if="removed" tone="default" :label="t('codes.statusRemoved')" />
              </p>
            </div>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <Button
              v-if="isOwner && !removed"
              variant="outline"
              size="sm"
              @click="router.push(`/codes/${share.id}/edit`)"
            >
              <PenLine class="size-4" />
              {{ t('codes.edit') }}
            </Button>
            <Button
              v-if="userStore.isLoggedIn && !isOwner && !removed"
              variant="outline"
              size="sm"
              @click="reportOpen = true"
            >
              {{ t('community.report.short') }}
            </Button>
            <Button v-if="canManage" variant="destructive" size="sm" @click="remove">
              <Trash2 class="size-4" />
              {{ t('codes.deleteTitle') }}
            </Button>
          </div>
        </header>

        <InlineNotice v-if="removed" tone="warning">
          {{ t('codes.deleteConfirm') }}
        </InlineNotice>

        <section v-if="share.description">
          <h2 class="text-lg font-medium">{{ t('codes.description') }}</h2>
          <div class="my-5 h-px bg-border" role="separator" />
          <MarkdownView :source="share.description" />
        </section>

        <section>
          <h2 class="text-lg font-medium">{{ t('codes.codeLabel') }}</h2>
          <div class="my-5 h-px bg-border" role="separator" />
          <CodeBlockView :code="share.code" :language="share.language" :title="languageLabel" />
        </section>

        <CommentThread target-type="code_share" :target-id="share.id" :disabled="removed" flat />
      </div>

      <ReportDialog v-model:open="reportOpen" target-type="code_share" :target-id="share.id" />
    </template>

    <div v-else class="list-empty">
      <EmptyState :icon="FileQuestion" :text="t('admin.codes.previewNotFound')" />
    </div>
  </PageShell>
</template>