<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, Loader2, PenLine, Trash2 } from '@lucide/vue'

import { deleteSolution, getSolution } from '@/api/community'
import CommentThread from '@/components/community/CommentThread.vue'
import ReportDialog from '@/components/community/ReportDialog.vue'
import InlineNotice from '@/components/common/InlineNotice.vue'
import MarkdownView from '@/components/common/MarkdownView.vue'
import { Card } from '@/components/ui/card'
import PageShell from '@/components/common/PageShell.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import { Button } from '@/components/ui/button'
import { useUserStore } from '@/stores/user'
import { confirmDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { SolutionDetail } from '@/types'
import { useSolutionContext } from './useSolutionContext'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()
const { solutionsBase } = useSolutionContext()

const solution = ref<SolutionDetail | null>(null)
const loading = ref(false)
const reportOpen = ref(false)

const solutionId = String(route.params.solutionId)
const isOwner = computed(() => solution.value?.author.id === userStore.user?.id)
const canManage = computed(() => isOwner.value || userStore.isAdmin)
const removed = computed(() => solution.value?.status === 'removed')

async function load(): Promise<void> {
  loading.value = true
  try {
    solution.value = await getSolution(solutionId)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    loading.value = false
  }
}

function edit(): void {
  void router.push(`${solutionsBase.value}/${solutionId}/edit`)
}

async function remove(): Promise<void> {
  const ok = await confirmDialog({
    title: t('problems.solutions.deleteTitle'),
    content: t('problems.solutions.deleteConfirm'),
    positiveText: t('problems.solutions.deleteTitle'),
    negativeText: t('action.cancel'),
    danger: true,
  })
  if (!ok) return
  try {
    await deleteSolution(solutionId)
    message.success(t('common.success'))
    void router.push(solutionsBase.value)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

onMounted(load)
</script>

<template>
  <PageShell width="narrow">
    <template #actions>
      <Button variant="outline" size="sm" @click="router.push(solutionsBase)">
        <ArrowLeft class="size-4" />
        {{ t('problems.solutions.backToList') }}
      </Button>
    </template>

    <div v-if="loading" class="grid min-h-[320px] place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <template v-else-if="solution">
      <Card class="overflow-hidden">
        <header class="border-b border-border px-5 py-4">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0">
              <h1 class="text-[20px] font-semibold leading-tight tracking-tight">
                {{ solution.title }}
              </h1>
              <p class="mt-2 flex flex-wrap items-center gap-2 text-[12.5px] text-muted-foreground">
                <span>{{ solution.author.nickname }}</span>
                <span aria-hidden="true">·</span>
                <span>{{ t('problems.solutions.editedAt', { time: formatDateTime(solution.updated_at) }) }}</span>
                <ToneBadge
                  v-if="removed"
                  tone="default"
                  :label="t('problems.solutions.status.removed')"
                />
              </p>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <Button v-if="userStore.isLoggedIn && !isOwner && !removed" variant="outline" size="sm" @click="reportOpen = true">
                {{ t('community.report.short') }}
              </Button>
              <Button v-if="canManage && !removed" variant="outline" size="sm" @click="edit">
                <PenLine class="size-4" />
                {{ t('action.edit') }}
              </Button>
              <Button v-if="canManage" variant="destructive" size="sm" @click="remove">
                <Trash2 class="size-4" />
                {{ t('problems.solutions.deleteTitle') }}
              </Button>
            </div>
          </div>
        </header>
        <div class="px-5 py-4">
          <InlineNotice v-if="removed" tone="warning" class="mb-4">
            {{ t('problems.solutions.removedLocked') }}
          </InlineNotice>
          <MarkdownView :source="solution.content" />
        </div>
      </Card>

      <div class="mt-4">
        <CommentThread
          target-type="solution"
          :target-id="solution.id"
          :disabled="removed"
        />
      </div>

      <ReportDialog v-model:open="reportOpen" target-type="solution" :target-id="solution.id" />
    </template>

    <Card v-else class="grid min-h-[320px] place-items-center">
      <p class="text-[13px] text-muted-foreground">{{ t('admin.solutions.previewNotFound') }}</p>
    </Card>
  </PageShell>
</template>