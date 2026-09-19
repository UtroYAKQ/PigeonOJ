<script setup lang="ts">
/**
 * 代码分享详情页（docs/contracts/community.md「代码广场」）：
 * 说明（Markdown）+ 只读代码（Monaco，复制用浏览器编辑器原生能力）+ 操作 + 评论区。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { deleteCodeShare, getCodeShare } from '@/api/community'
import BaseAvatar from '@/components/BaseAvatar.vue'
import CodeEditor from '@/components/CodeEditor.vue'
import ReportDialog from '@/components/community/ReportDialog.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { languageOptions } from '@/constants/languages'
import { useUserStore } from '@/stores/user'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { CodeShareDetail } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const shareId = computed(() => String(route.params.id))
const share = ref<CodeShareDetail | null>(null)
const loading = ref(false)
const reportVisible = ref(false)

const isOwner = computed(() => share.value && share.value.author.id === userStore.user?.id)

function languageLabel(value: string) {
  return languageOptions.find((o) => o.value === value)?.label ?? value
}

async function load() {
  loading.value = true
  try {
    share.value = await getCodeShare(shareId.value)
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
  } finally {
    loading.value = false
  }
}

function remove() {
  confirmAsyncDialog({
    title: t('codes.deleteTitle'),
    content: t('codes.deleteConfirm'),
    positiveText: t('action.confirm'),
    action: () => deleteCodeShare(shareId.value),
    successMessage: t('common.success'),
    onAfterSuccess: () => {
      void router.push('/codes')
    },
  })
}

function goBack() {
  void router.push('/codes')
}

onMounted(load)
</script>

<template>
  <WorkbenchShell>
    <template #header-extra>
      <n-button secondary @click="goBack">
        {{ t('codes.backToList') }}
      </n-button>
    </template>

    <n-spin :show="loading" class="table-fill" content-style="height: 100%; overflow: auto">
      <div v-if="share" class="share-detail">
        <div class="share-detail__header">
          <BaseAvatar
            :src="share.author.avatar_url ?? undefined"
            :name="share.author.nickname"
            :size="40"
          />
          <div class="share-detail__byline">
            <h2 class="share-detail__title">{{ share.title }}</h2>
            <div class="share-detail__meta">
              <span class="share-detail__author">{{ share.author.nickname }}</span>
              <span>{{ formatDateTime(share.created_at) }}</span>
              <n-tag size="small" type="info" bordered>{{ languageLabel(share.language) }}</n-tag>
              <n-tag v-if="share.status === 'removed'" size="small" type="warning" bordered>
                {{ t('codes.statusRemoved') }}
              </n-tag>
            </div>
          </div>
          <span class="share-detail__spacer" />
          <div v-if="userStore.isLoggedIn" class="share-detail__actions">
            <n-button v-if="isOwner" text size="small" type="error" @click="remove">
              {{ t('action.delete') }}
            </n-button>
            <n-button v-if="!isOwner" text size="small" @click="reportVisible = true">
              {{ t('community.report.short') }}
            </n-button>
          </div>
        </div>

        <p v-if="share.description" class="share-detail__description">
          {{ share.description }}
        </p>

        <div class="share-detail__code">
          <CodeEditor :model-value="share.code" :language="share.language" read-only />
        </div>
      </div>
      <div v-else class="table-fill-empty share-detail__empty">
        {{ loading ? '' : t('common.loadFailed') }}
      </div>
    </n-spin>

    <ReportDialog v-model:show="reportVisible" target-type="code_share" :target-id="shareId" />
  </WorkbenchShell>
</template>

<style scoped>
.share-detail {
  max-width: 960px;
  margin: 0 auto;
  padding-bottom: 24px;
}
.share-detail__header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.share-detail__byline {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.share-detail__title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  line-height: 1.4;
}
.share-detail__meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.share-detail__author {
  font-weight: 600;
  color: var(--app-text);
}
.share-detail__problem {
  padding: 2px 10px;
  border-radius: 999px;
  background: var(--app-muted-bg);
  cursor: pointer;
  transition: color 0.15s;
}
.share-detail__problem:hover {
  color: var(--app-primary);
}
.share-detail__spacer {
  flex: 1;
}
.share-detail__actions {
  display: flex;
  gap: 12px;
}
.share-detail__description {
  margin-top: 14px;
  font-size: 13.5px;
  line-height: 1.8;
  color: var(--app-text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}
.share-detail__code {
  margin-top: 14px;
}
.share-detail__code :deep(.code-editor) {
  height: 480px;
}
.share-detail__empty {
  color: var(--app-text-secondary);
}
</style>
