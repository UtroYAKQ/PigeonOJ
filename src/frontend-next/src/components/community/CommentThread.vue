<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ImagePlus, Loader2, MessageSquare, Send, Smile } from '@lucide/vue'


import { uploadImage } from '@/api/files'
import { adminSetCommentStatus, createComment, deleteComment, listComments } from '@/api/community'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import LineList from '@/components/common/LineList.vue'
import ReportDialog from '@/components/community/ReportDialog.vue'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { InputGroup, InputGroupTextarea } from '@/components/ui/input-group'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
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
    /** 无卡片外框：嵌入详情页时与页面平铺对齐 */
    flat?: boolean
  }>(),
  { disabled: false, adminMode: false, flat: false },
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

/** 输入框增强：表情 / 图片（图片入库为 Markdown 语法，渲染走本站文件白名单） */
/** 基础常用表情，避免引入整套表情数据集 */
const BASIC_EMOJIS = [
  '😀', '😄', '😁', '😆', '😅', '😂', '🤣', '😊',
  '😇', '🙂', '😉', '😍', '🥰', '😘', '😋', '😜',
  '🤪', '😝', '🤗', '🤔', '🤨', '😐', '😶', '🙄',
  '😏', '😥', '😮', '😯', '😴', '😌', '🥳', '😎',
  '🤓', '🧐', '👍', '👎', '👏', '🙏', '💪', '🤝',
  '👋', '❤️', '🔥', '🎉', '✅', '❌', '⭐', '💯',
]
const IMAGE_ACCEPT = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
const MAX_IMAGE_BYTES = 5 * 1024 * 1024
const composerRef = ref<{ $el?: HTMLTextAreaElement }>()
const fileInput = ref<HTMLInputElement>()
const emojiOpen = ref(false)
const uploading = ref(false)

function composerElement(): HTMLTextAreaElement | undefined {
  return (composerRef.value as { $el?: HTMLTextAreaElement } | undefined)?.$el
}

function insertText(text: string): void {
  const el = composerElement()
  if (!el) {
    content.value += text
    return
  }
  const start = el.selectionStart ?? content.value.length
  const end = el.selectionEnd ?? content.value.length
  content.value = content.value.slice(0, start) + text + content.value.slice(end)
  void nextTick(() => {
    el.focus()
    const pos = start + text.length
    el.setSelectionRange(pos, pos)
  })
}

function onEmojiSelect(emoji: string): void {
  insertText(emoji)
  emojiOpen.value = false
}

function pickImage(): void {
  fileInput.value?.click()
}

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  if (files.length) void uploadFiles(files)
}

async function uploadFiles(files: File[]): Promise<void> {
  const valid = files.filter((file) => IMAGE_ACCEPT.includes(file.type))
  if (!valid.length) {
    message.error(t('common.imageTypeInvalid'))
    return
  }
  uploading.value = true
  const tip = message.loading(t('common.imageUploading'))
  try {
    for (const file of valid) {
      if (file.size > MAX_IMAGE_BYTES) {
        message.error(t('common.imageTooLarge'))
        continue
      }
      try {
        const result = await uploadImage(file)
        insertText(`\n![${file.name}](${result.url})\n`)
      } catch (error) {
        message.error(error instanceof Error ? error.message : t('common.imageUploadFailed'))
      }
    }
  } finally {
    tip.destroy()
    uploading.value = false
  }
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/** 评论内容渲染：全部 HTML 转义，仅放行本站上传图片的 Markdown 语法 */
function renderContent(text: string): string {
  return escapeHtml(text).replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, (match, alt, url) => {
    if (!/^\/api\/v1\/files\/[A-Za-z0-9_./-]+$/.test(url)) return match
    return `<img src="${url}" alt="${alt}" loading="lazy" class="mt-1 max-h-[240px] max-w-full border border-border object-contain" />`
  })
}

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
  void nextTick(() => {
    const el = composerElement()
    el?.focus()
    el?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  })
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
  <component :is="flat ? 'div' : Card">
    <header
      class="flex items-center gap-2 border-b border-border py-3"
      :class="{ 'px-4': !flat }"
    >
      <MessageSquare class="size-4 text-muted-foreground" />
      <h2 class="text-[13.5px] font-semibold">{{ t('community.comment.title') }}</h2>
      <span class="text-[12px] tabular-nums text-muted-foreground">{{ total }}</span>
    </header>

    <div class="space-y-3 py-3" :class="{ 'px-4': !flat }">

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
                <div
                  v-if="node.content != null"
                  class="mt-1 whitespace-pre-wrap break-words text-[13px] leading-6"
                  v-html="renderContent(node.content)"
                />
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
                    <div class="flex items-start gap-2">
                      <BaseAvatar
                        :src="reply.author?.avatar_url"
                        :name="authorName(reply)"
                        :size="20"
                        class="mt-0.5 shrink-0"
                      />
                      <div class="min-w-0 flex-1">
                        <div class="flex flex-wrap items-center gap-2">
                          <span class="font-medium">{{ authorName(reply) }}</span>
                          <span class="tabular-nums text-muted-foreground">
                            {{ formatDateTime(reply.created_at) }}
                          </span>
                        </div>
                        <div
                          v-if="reply.content != null"
                          class="mt-0.5 whitespace-pre-wrap break-words leading-5"
                          v-html="renderContent(reply.content)"
                        />
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
                      </div>
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

    <div
      v-if="userStore.isLoggedIn"
      class="sticky bottom-0 z-10 border-t border-border bg-background/95 py-3 backdrop-blur"
      :class="{ 'px-4': !flat }"
    >
      <div v-if="replyTo" class="mb-2 flex items-center gap-2 text-[12px] text-muted-foreground">
        {{ t('community.comment.replyingTo', { name: replyTo.name }) }}
        <button type="button" class="text-brand hover:underline" @click="cancelReply">
          {{ t('action.cancel') }}
        </button>
      </div>
      <InputGroup class="min-w-0 flex-1 flex-col items-stretch">
          <InputGroupTextarea
            ref="composerRef"
            v-model="content"
            rows="2"
            maxlength="2000"
            :placeholder="
              replyTo
                ? t('community.comment.replyPlaceholder', { name: replyTo.name })
                : t('community.comment.placeholder')
            "
          />
          <div class="flex items-center justify-between gap-2 border-t border-border/60 px-2 py-1">
            <div class="flex items-center gap-0.5">
              <Popover v-model:open="emojiOpen">
                <PopoverTrigger as-child>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    class="size-7"
                    :title="t('community.comment.emoji')"
                  >
                    <Smile class="size-4" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent
                  side="top"
                  align="start"
                  class="w-auto border-0 bg-transparent p-0 shadow-none ring-0"
                >
                  <div class="grid w-[272px] grid-cols-8 gap-0.5 border border-border bg-background p-2">
                    <button
                      v-for="emoji in BASIC_EMOJIS"
                      :key="emoji"
                      type="button"
                      class="flex size-8 items-center justify-center text-[20px] leading-none hover:bg-muted"
                      @click="onEmojiSelect(emoji)"
                    >
                      {{ emoji }}
                    </button>
                  </div>
                </PopoverContent>
              </Popover>
              <input
                ref="fileInput"
                type="file"
                class="hidden"
                :accept="IMAGE_ACCEPT.join(',')"
                @change="onFileChange"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                class="size-7"
                :title="t('community.comment.image')"
                :disabled="uploading"
                @click="pickImage"
              >
                <Loader2 v-if="uploading" class="size-4 animate-spin" />
                <ImagePlus v-else class="size-4" />
              </Button>
            </div>
            <Button size="sm" class="h-7 px-3" :disabled="submitting || disabled" @click="submit">
              <Loader2 v-if="submitting" class="size-3.5 animate-spin" />
              <Send v-else class="size-3.5" />
              {{ t('community.comment.submit') }}
            </Button>
          </div>
        </InputGroup>
    </div>
    <p v-else class="py-3 text-[12.5px] text-muted-foreground" :class="{ 'px-4': !flat }">
      {{ t('community.comment.loginHint') }}
    </p>

    <ReportDialog v-model:open="reportOpen" target-type="comment" :target-id="reportTargetId" />
  </component>
</template>
