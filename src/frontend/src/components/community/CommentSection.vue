<script setup lang="ts">
/**
 * 多态评论区（docs/contracts/community.md comments）：一级评论分页 + 回复预览 +
 * 「查看全部回复」；发表 / 回复（两级，parent_id 仅挂一级评论）、软删（owner / admin）、
 * 恢复（admin）、举报。管理端题解预览传 admin-mode 含被删评论并开放恢复。
 */
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { InputInst } from 'naive-ui'

import { adminSetCommentStatus, createComment, deleteComment, listComments } from '@/api/community'
import BaseAvatar from '@/components/BaseAvatar.vue'
import ReportDialog from '@/components/community/ReportDialog.vue'
import { usePagination } from '@/composables/usePagination'
import { useUserStore } from '@/stores/user'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { CommentNode, CommentTargetType } from '@/types'

const props = withDefaults(
  defineProps<{
    targetType: CommentTargetType
    targetId: string
    /** 管理端模式：请求含被删评论（include_deleted，仅 admin 生效）并开放恢复 */
    adminMode?: boolean
    /** 高亮定位的评论 id（举报处理跳转锚定） */
    highlightCommentId?: string | null
  }>(),
  { adminMode: false, highlightCommentId: null },
)

const { t } = useI18n()
const userStore = useUserStore()

const loading = ref(false)
const items = ref<CommentNode[]>([])
const paging = usePagination({ defaultPageSize: 10 })
/** 「查看全部回复」展开后的完整回复列表（未展开时用后端预览的前 2 条） */
const expandedReplies = reactive<Record<string, CommentNode[]>>({})
const replyTo = ref<CommentNode | null>(null)
const content = ref('')
const submitting = ref(false)
const composerOpen = ref(false)
const composerInput = ref<InputInst | null>(null)
const reportVisible = ref(false)
const reportTargetId = ref('')

const canComment = computed(() => userStore.isLoggedIn)
const replyPlaceholder = computed(() =>
  replyTo.value
    ? t('community.comment.replyPlaceholder', { name: replyTo.value.author?.nickname ?? '' })
    : t('community.comment.placeholder'),
)

async function load() {
  const seq = paging.beginLoad()
  loading.value = true
  try {
    const res = await listComments({
      target_type: props.targetType,
      target_id: props.targetId,
      page: paging.page.value,
      page_size: paging.pageSize.value,
      include_deleted: props.adminMode || undefined,
    })
    if (!paging.isCurrent(seq)) return
    items.value = res.items
    paging.total.value = res.total
    if (props.highlightCommentId) scheduleHighlight()
  } catch (e) {
    if (!paging.isCurrent(seq)) return
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
  } finally {
    if (paging.isCurrent(seq)) loading.value = false
  }
}

function onPage(p: number) {
  paging.changePage(p)
  load()
}

function highlightTarget(): HTMLElement | null {
  const id = props.highlightCommentId
  if (!id) return null
  return document.querySelector(`[data-comment-id="${id}"]`)
}

function scheduleHighlight() {
  requestAnimationFrame(() => {
    const el = highlightTarget()
    if (!el) return
    el.scrollIntoView({ block: 'center' })
    el.classList.add('comment--highlight')
  })
}

async function submit() {
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
    content.value = ''
    replyTo.value = null
    composerOpen.value = false
    message.success(t('community.comment.sent'))
    // 回复直接命中预览需重置到能看到的口径：保持当前页刷新即可
    await load()
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.operationFailed'))
  } finally {
    submitting.value = false
  }
}

/** 评论框默认折叠为占位条，点击 / 回复时展开并聚焦（降低展开卡片的视觉噪音） */
function openComposer() {
  composerOpen.value = true
  void nextTick(() => composerInput.value?.focus())
}

function closeComposer() {
  composerOpen.value = false
  content.value = ''
  replyTo.value = null
}

function startReply(comment: CommentNode) {
  replyTo.value = comment
  openComposer()
}

function cancelReply() {
  replyTo.value = null
}

function canModerate(comment: CommentNode): boolean {
  return userStore.isAdmin || comment.author?.id === userStore.user?.id
}

function removeComment(comment: CommentNode) {
  confirmAsyncDialog({
    title: t('community.comment.deleteTitle'),
    content: t('community.comment.deleteConfirm'),
    positiveText: t('action.confirm'),
    action: () => deleteComment(comment.id),
    successMessage: t('common.success'),
    onAfterSuccess: () => load(),
  })
}

async function restoreComment(comment: CommentNode) {
  try {
    await adminSetCommentStatus(comment.id, false)
    message.success(t('common.success'))
    await load()
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.operationFailed'))
  }
}

function visibleReplies(comment: CommentNode): CommentNode[] {
  return expandedReplies[comment.id] ?? comment.replies
}

async function expandReplies(comment: CommentNode) {
  if (expandedReplies[comment.id]) return
  try {
    const res = await listComments({
      target_type: props.targetType,
      target_id: props.targetId,
      parent_id: comment.id,
      page_size: 100,
      include_deleted: props.adminMode || undefined,
    })
    expandedReplies[comment.id] = res.items
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
  }
}

function openReport(comment: CommentNode) {
  reportTargetId.value = comment.id
  reportVisible.value = true
}

onMounted(load)
</script>

<template>
  <section class="comment-section">
    <h3 class="comment-section__title">
      {{ t('community.comment.title') }}
      <span v-if="paging.total.value" class="comment-section__count">{{ paging.total.value }}</span>
    </h3>

    <!-- 评论列表 -->
    <n-spin :show="loading">
      <div v-if="items.length" class="comment-list">
        <article v-for="item in items" :key="item.id" class="comment" :data-comment-id="item.id">
          <div class="comment__main">
            <BaseAvatar
              :src="item.author?.avatar_url ?? undefined"
              :name="item.author?.nickname ?? t('community.comment.deletedAuthor')"
              :size="32"
            />
            <div class="comment__body">
              <div class="comment__meta">
                <span class="comment__author">
                  {{ item.author?.nickname ?? t('community.comment.deletedAuthor') }}
                </span>
                <span class="comment__time">{{ formatDateTime(item.created_at) }}</span>
                <span v-if="item.is_deleted" class="comment__deleted-tag">
                  {{ t('community.comment.deletedTag') }}
                </span>
              </div>
              <p class="comment__content" :class="{ 'comment__content--deleted': item.is_deleted }">
                {{ item.is_deleted ? t('community.comment.deletedContent') : item.content }}
              </p>
              <div v-if="!item.is_deleted" class="comment__actions">
                <n-button v-if="canComment" text size="tiny" @click="startReply(item)">
                  {{ t('community.comment.reply') }}
                </n-button>
                <n-button
                  v-if="canModerate(item) && !item.is_deleted"
                  text
                  size="tiny"
                  type="error"
                  @click="removeComment(item)"
                >
                  {{ t('action.delete') }}
                </n-button>
                <n-button
                  v-if="adminMode && item.is_deleted"
                  text
                  size="tiny"
                  type="success"
                  @click="restoreComment(item)"
                >
                  {{ t('community.comment.restore') }}
                </n-button>
                <n-button
                  v-if="canComment && item.author && item.author.id !== userStore.user?.id"
                  text
                  size="tiny"
                  @click="openReport(item)"
                >
                  {{ t('community.report.short') }}
                </n-button>
              </div>
            </div>
          </div>

          <!-- 回复（两级：回复不可再被回复） -->
          <div v-if="visibleReplies(item).length" class="comment__replies">
            <div
              v-for="reply in visibleReplies(item)"
              :key="reply.id"
              class="comment comment--reply"
              :data-comment-id="reply.id"
            >
              <BaseAvatar
                :src="reply.author?.avatar_url ?? undefined"
                :name="reply.author?.nickname ?? t('community.comment.deletedAuthor')"
                :size="26"
              />
              <div class="comment__body">
                <div class="comment__meta">
                  <span class="comment__author">
                    {{ reply.author?.nickname ?? t('community.comment.deletedAuthor') }}
                  </span>
                  <span class="comment__time">{{ formatDateTime(reply.created_at) }}</span>
                </div>
                <p
                  class="comment__content"
                  :class="{ 'comment__content--deleted': reply.is_deleted }"
                >
                  {{ reply.is_deleted ? t('community.comment.deletedContent') : reply.content }}
                </p>
                <div v-if="!reply.is_deleted" class="comment__actions">
                  <n-button
                    v-if="canModerate(reply)"
                    text
                    size="tiny"
                    type="error"
                    @click="removeComment(reply)"
                  >
                    {{ t('action.delete') }}
                  </n-button>
                  <n-button
                    v-if="adminMode && reply.is_deleted"
                    text
                    size="tiny"
                    type="success"
                    @click="restoreComment(reply)"
                  >
                    {{ t('community.comment.restore') }}
                  </n-button>
                  <n-button
                    v-if="canComment && reply.author && reply.author.id !== userStore.user?.id"
                    text
                    size="tiny"
                    @click="openReport(reply)"
                  >
                    {{ t('community.report.short') }}
                  </n-button>
                </div>
              </div>
            </div>
          </div>

          <n-button
            v-if="item.reply_count > visibleReplies(item).length"
            text
            size="tiny"
            type="primary"
            class="comment__expand"
            @click="expandReplies(item)"
          >
            {{ t('community.comment.viewAllReplies', { count: item.reply_count }) }}
          </n-button>
        </article>
      </div>
      <div v-else class="comment-empty">
        {{ t('community.comment.emptyText') }}
      </div>
    </n-spin>

    <div v-if="paging.total.value > paging.pageSize.value" class="comment-pagination">
      <n-pagination
        :page="paging.page.value"
        :page-size="paging.pageSize.value"
        :item-count="paging.total.value"
        simple
        @update:page="onPage"
      />
    </div>

    <!-- 发表 / 回复框置于评论区最下方：先读别人的评论，再写自己的 -->
    <div v-if="canComment" class="comment-composer">
      <div
        v-if="!composerOpen"
        class="comment-composer__stub"
        role="button"
        tabindex="0"
        @click="openComposer"
        @keydown.enter="openComposer"
      >
        {{
          replyTo
            ? t('community.comment.replyPlaceholder', { name: replyTo.author?.nickname ?? '' })
            : t('community.comment.placeholder')
        }}
      </div>
      <template v-else>
        <div v-if="replyTo" class="comment-composer__replying">
          {{ t('community.comment.replyingTo', { name: replyTo.author?.nickname ?? '' }) }}
          <n-button text size="tiny" @click="cancelReply">
            {{ t('action.cancel') }}
          </n-button>
        </div>
        <n-input
          ref="composerInput"
          v-model:value="content"
          type="textarea"
          maxlength="2000"
          show-count
          :placeholder="replyPlaceholder"
          :autosize="{ minRows: 3, maxRows: 6 }"
        />
        <div class="comment-composer__actions">
          <n-button size="small" quaternary @click="closeComposer">
            {{ t('action.cancel') }}
          </n-button>
          <n-button type="primary" size="small" :loading="submitting" @click="submit">
            {{ t('community.comment.submit') }}
          </n-button>
        </div>
      </template>
    </div>
    <n-alert v-else type="info" :show-icon="false" class="comment-login-hint">
      {{ t('community.comment.loginHint') }}
    </n-alert>

    <ReportDialog v-model:show="reportVisible" target-type="comment" :target-id="reportTargetId" />
  </section>
</template>

<style scoped>
.comment-section {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--app-border);
}
.comment-section__title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
}
.comment-section__count {
  color: var(--app-text-secondary);
  font-size: 12px;
  font-weight: normal;
}
.comment-composer {
  margin-top: 14px;
}
/* 折叠占位条：低调的一行输入样式，点击展开完整编辑区 */
.comment-composer__stub {
  padding: 10px 14px;
  border: 1px solid var(--app-border);
  border-radius: 3px;
  font-size: 13px;
  color: var(--app-text-secondary);
  cursor: text;
  transition: border-color 0.15s;
}
.comment-composer__stub:hover {
  border-color: var(--app-primary);
}
.comment-composer__replying {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.comment-composer__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}
.comment-login-hint {
  margin-top: 14px;
}
.comment {
  padding: 12px 0;
  border-top: 1px solid var(--app-border);
}
.comment--highlight {
  animation: comment-highlight 2s ease-out;
}
@keyframes comment-highlight {
  0% {
    background: var(--app-muted-bg);
  }
  100% {
    background: transparent;
  }
}
.comment__main {
  display: flex;
  gap: 10px;
}
.comment__body {
  flex: 1;
  min-width: 0;
}
.comment__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}
.comment__author {
  font-weight: 600;
}
.comment__time {
  color: var(--app-text-secondary);
}
.comment__deleted-tag {
  color: var(--app-text-secondary);
}
.comment__content {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}
.comment__content--deleted {
  color: var(--app-text-secondary);
  font-style: italic;
}
.comment__actions {
  display: flex;
  gap: 10px;
  margin-top: 4px;
}
.comment__replies {
  margin: 8px 0 0 42px;
  border-left: 2px solid var(--app-border);
  padding-left: 12px;
}
.comment--reply {
  border-top: none;
  padding: 8px 0;
  display: flex;
  gap: 8px;
}
.comment__expand {
  margin: 2px 0 0 42px;
}
.comment-empty {
  padding: 24px 0;
  text-align: center;
  color: var(--app-text-secondary);
  font-size: 13px;
}
.comment-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
</style>
