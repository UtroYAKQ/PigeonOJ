<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, MessageSquare, Send } from '@lucide/vue'

import { adminSetCommentStatus, createComment, deleteComment, listComments } from '@/api/community'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import LineList from '@/components/common/LineList.vue'
import ReportDialog from '@/components/community/ReportDialog.vue'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useUserStore } from '@/stores/user'
import { confirmDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { CommentNode, CommentTargetType } from '@/types'

const props = withDefaults(
  defineProps<{
    targetType: CommentTargetType
    targetId: string
    disabled?: boolean
    adminMode?: boolean
  }>(),
  { disabled: false, adminMode: false },
)

const { t } = useI18n()
const userStore = useUserStore()

const comments = ref<CommentNode[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = 10
const total = ref(0)

const content = ref('')
const submitting = ref(false)
const replyTo = ref<{ id: string; name: string } | null>(null)

const expanded = ref<Record<string, CommentNode[] | undefined>>({})
const replyLoading = ref<Record<string, boolean>>({})

const reportOpen = ref(false)
const reportTargetId = ref('')

async function load(): Promise<void> {
  loading.value = true
  try {
    const result = await listComments({
      target_type: props.targetType,
      target_id: props.targetId,
      page: page.value,
      page_size: pageSize,
      include_deleted: props.adminMode || undefined,
    })
    comments.value = result.items
    total.value = result.total
    expanded.value = {}
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    loading.value = false
  }
}

function changePage(value: number): void {
  page.value = value
  void load()
}

function authorName(node: CommentNode): string {
  return node.author?.nickname ?? t('community.comment.deletedAuthor')
}

function beginReply(node: CommentNode): void {
  replyTo.value = { id: node.parent_id ?? node.id, name: authorName(node) }
}

function cancelReply(): void {
  replyTo.value = null
}

async function submit(): Promise<void> {
  const text = content.value.trim()
  if (!text) {
    message.warning(t('community.comment.empty'))
    return
  }
  if (text.length > 2000) {
    message.warning(t('community.comment.tooLong'))
    return
  }
  submitting.value = true
  try {
    await createComment({
      target_type: props.targetType,
      target_id: props.targetId,
      parent_id: replyTo.value?.id,
      content: text,
    })
    message.success(t('community.comment.sent'))
    content.value = ''
    replyTo.value = null
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    submitting.value = false
  }
}

async function toggleReplies(node: CommentNode): Promise<void> {
  if (expanded.value[node.id]) {
    delete expanded.value[node.id]
    expanded.value = { ...expanded.value }
    return
  }
  replyLoading.value[node.id] = true
  try {
    const result = await listComments({
      target_type: props.targetType,
      target_id: props.targetId,
      parent_id: node.id,
      page: 1,
      page_size: 100,
      include_deleted: props.adminMode || undefined,
    })
    expanded.value[node.id] = result.items
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    replyLoading.value[node.id] = false
  }
}

async function removeComment(node: CommentNode): Promise<void> {
  const ok = await confirmDialog({
    title: t('community.comment.deleteTitle'),
    content: t('community.comment.deleteConfirm'),
    positiveText: t('action.delete'),
    negativeText: t('action.cancel'),
    danger: true,
  })
  if (!ok) return
  try {
    await deleteComment(node.id)
    message.success(t('common.success'))
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

async function restoreComment(node: CommentNode): Promise<void> {
  try {
    await adminSetCommentStatus(node.id, false)
    message.success(t('community.comment.restore'))
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

function openReport(node: CommentNode): void {
  reportTargetId.value = node.id
  reportOpen.value = true
}

onMounted(load)
</script>

<template>
  <section class="rounded-xl border border-border bg-card">
    <header class="flex items-center gap-2 border-b border-border px-4 py-3">
      <MessageSquare class="size-4 text-muted-foreground" />
      <h2 class="text-[13.5px] font-semibold">{{ t('community.comment.title') }}</h2>
      <span class="text-[12px] tabular-nums text-muted-foreground">{{ total }}</span>
    </header>

    <div class="space-y-3 px-4 py-3">
      <div v-if="userStore.isLoggedIn" class="space-y-2">
        <p v-if="replyTo" class="flex items-center gap-2 text-[12px] text-muted-foreground">
          {{ t('community.comment.replyingTo', { name: replyTo.name }) }}
          <button type="button" class="text-brand hover:underline" @click="cancelReply">
            {{ t('action.cancel') }}
          </button>
        </p>
        <Textarea
          v-model="content"
          rows="3"
          maxlength="2000"
          class="min-h-[84px] text-[13px]"
          :placeholder="
            replyTo
              ? t('community.comment.replyPlaceholder', { name: replyTo.name })
              : t('community.comment.placeholder')
          "
        />
        <div class="flex justify-end">
          <Button size="sm" :disabled="submitting || disabled" @click="submit">
            <Loader2 v-if="submitting" class="size-3.5 animate-spin" />
            <Send v-else class="size-3.5" />
            {{ t('community.comment.submit') }}
          </Button>
        </div>
      </div>
      <p v-else class="text-[12.5px] text-muted-foreground">
        {{ t('community.comment.loginHint') }}
      </p>

      <LineList
        :items="comments"
        :loading="loading && !comments.length"
        :empty-text="t('community.comment.emptyText')"
        :get-key="(node: CommentNode) => node.id"
        :show-pager="total > pageSize"
        :total="total"
        :page="page"
        :page-size="pageSize"
        @update:page="changePage"
      >
        <template #skeleton>
          <div class="grid h-24 place-items-center">
            <Loader2 class="size-6 animate-spin text-muted-foreground" />
          </div>
        </template>
        <template #item="{ item: node }">
          <div class="py-3.5">
            <div class="flex items-start gap-2.5">
              <BaseAvatar :src="node.author?.avatar_url" :name="authorName(node)" :size="28" />
              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="text-[12.5px] font-medium">{{ authorName(node) }}</span>
                  <span class="text-[11.5px] tabular-nums text-muted-foreground">
                    {{ formatDateTime(node.created_at) }}
                  </span>
                  <span
                    v-if="node.is_deleted"
                    class="rounded border border-border bg-muted px-1.5 text-[10px] text-muted-foreground"
                  >
                    {{ t('community.comment.deletedTag') }}
                  </span>
                </div>
                <p
                  v-if="node.content != null"
                  class="mt-1 whitespace-pre-wrap break-words text-[13px] leading-6"
                >
                  {{ node.content }}
                </p>
                <p v-else class="mt-1 text-[13px] italic text-muted-foreground">
                  {{ t('community.comment.deletedContent') }}
                </p>

                <div
                  class="mt-1.5 flex flex-wrap items-center gap-3 text-[12px] text-muted-foreground"
                >
                  <button
                    v-if="userStore.isLoggedIn && !node.is_deleted && !node.parent_id"
                    type="button"
                    class="transition-colors hover:text-foreground"
                    @click="beginReply(node)"
                  >
                    {{ t('community.comment.reply') }}
                  </button>
                  <button
                    v-if="node.is_deleted && adminMode"
                    type="button"
                    class="transition-colors hover:text-foreground"
                    @click="restoreComment(node)"
                  >
                    {{ t('community.comment.restore') }}
                  </button>
                  <button
                    v-if="!node.is_deleted && userStore.isLoggedIn"
                    type="button"
                    class="transition-colors hover:text-foreground"
                    @click="openReport(node)"
                  >
                    {{ t('community.report.short') }}
                  </button>
                  <button
                    v-if="
                      !node.is_deleted &&
                      userStore.isLoggedIn &&
                      (node.author?.id === userStore.user?.id || adminMode)
                    "
                    type="button"
                    class="transition-colors hover:text-destructive"
                    @click="removeComment(node)"
                  >
                    {{ t('action.delete') }}
                  </button>
                  <button
                    v-if="node.reply_count > 0"
                    type="button"
                    class="transition-colors hover:text-foreground"
                    @click="toggleReplies(node)"
                  >
                    {{ t('community.comment.viewAllReplies', { count: node.reply_count }) }}
                  </button>
                </div>

                <ul
                  v-if="node.replies.length || expanded[node.id]"
                  class="mt-2.5 space-y-2.5 border-l-2 border-border pl-3"
                >
                  <li
                    v-for="reply in expanded[node.id] ?? node.replies"
                    :key="reply.id"
                    class="text-[12.5px]"
                  >
                    <div class="flex flex-wrap items-center gap-2">
                      <span class="font-medium">{{ authorName(reply) }}</span>
                      <span class="tabular-nums text-muted-foreground">
                        {{ formatDateTime(reply.created_at) }}
                      </span>
                    </div>
                    <p
                      v-if="reply.content != null"
                      class="mt-0.5 whitespace-pre-wrap break-words leading-5"
                    >
                      {{ reply.content }}
                    </p>
                    <p v-else class="mt-0.5 italic text-muted-foreground">
                      {{ t('community.comment.deletedContent') }}
                    </p>
                    <div class="mt-1 flex items-center gap-3 text-[11.5px] text-muted-foreground">
                      <button
                        v-if="!reply.is_deleted && userStore.isLoggedIn"
                        type="button"
                        class="hover:text-foreground"
                        @click="openReport(reply)"
                      >
                        {{ t('community.report.short') }}
                      </button>
                      <button
                        v-if="
                          !reply.is_deleted &&
                          userStore.isLoggedIn &&
                          (reply.author?.id === userStore.user?.id || adminMode)
                        "
                        type="button"
                        class="hover:text-destructive"
                        @click="removeComment(reply)"
                      >
                        {{ t('action.delete') }}
                      </button>
                    </div>
                  </li>
                </ul>
                <div
                  v-if="replyLoading[node.id]"
                  class="mt-2 flex items-center gap-1.5 text-[12px] text-muted-foreground"
                >
                  <Loader2 class="size-3.5 animate-spin" />
                  {{ t('common.loading') }}
                </div>
              </div>
            </div>
          </div>
        </template>
      </LineList>
    </div>

    <ReportDialog v-model:open="reportOpen" target-type="comment" :target-id="reportTargetId" />
  </section>
</template>
