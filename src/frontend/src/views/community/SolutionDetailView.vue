<script setup lang="ts">
/**
 * 题解详情页（docs/contracts/community.md）：全文渲染 + 本人编辑 / 删除 + 举报 + 评论区。
 * 上下文取参复用题解页口径（problemId ?? id），返回与跳转封闭在当前上下文。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { deleteSolution, getSolution } from '@/api/community'
import BaseAvatar from '@/components/BaseAvatar.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import CommentSection from '@/components/community/CommentSection.vue'
import ReportDialog from '@/components/community/ReportDialog.vue'
import { useUserStore } from '@/stores/user'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { SolutionDetail } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const problemId = computed(() => String(route.params.problemId ?? route.params.id))
const solutionId = computed(() => String(route.params.solutionId))
const problemPath = computed(() => {
  if (route.params.orgId) {
    return `/me/orgs/${String(route.params.orgId)}/problems/${problemId.value}`
  }
  if (route.params.setId) {
    return `/problem-sets/${String(route.params.setId)}/problems/${problemId.value}`
  }
  if (route.params.cid) {
    return `/contests/${String(route.params.cid)}/problems/${problemId.value}`
  }
  return `/problems/${problemId.value}`
})
const solutionsBase = computed(() => `${problemPath.value}/solutions`)

const solution = ref<SolutionDetail | null>(null)
const loading = ref(false)
const reportVisible = ref(false)

const isOwner = computed(() => solution.value && solution.value.author.id === userStore.user?.id)
const canReport = computed(() => userStore.isLoggedIn && solution.value && !isOwner.value)

async function load() {
  loading.value = true
  try {
    solution.value = await getSolution(solutionId.value)
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
  } finally {
    loading.value = false
  }
}

function edit() {
  void router.push(`${solutionsBase.value}/${solutionId.value}/edit`)
}

function remove() {
  confirmAsyncDialog({
    title: t('problems.solutions.deleteTitle'),
    content: t('problems.solutions.deleteConfirm'),
    positiveText: t('action.confirm'),
    action: () => deleteSolution(solutionId.value),
    successMessage: t('common.success'),
    onAfterSuccess: () => {
      void router.push(solutionsBase.value)
    },
  })
}

function goBack() {
  void router.push(solutionsBase.value)
}

onMounted(load)
</script>

<template>
  <WorkbenchShell :title="t('problems.solutions.detailTitle')">
    <template #header-extra>
      <n-button secondary @click="goBack">
        {{ t('problems.solutions.backToList') }}
      </n-button>
    </template>

    <n-spin :show="loading" class="table-fill" content-style="height: 100%; overflow: auto">
      <div v-if="solution" class="solution-detail">
        <h2 class="solution-detail__title">
          {{ solution.title }}
          <n-tag v-if="solution.status === 'removed'" size="small" type="error" bordered>
            {{ t(`problems.solutions.status.${solution.status}`) }}
          </n-tag>
        </h2>
        <div class="solution-detail__meta">
          <BaseAvatar
            :src="solution.author.avatar_url ?? undefined"
            :name="solution.author.nickname"
            :size="30"
          />
          <span class="solution-detail__author">{{ solution.author.nickname }}</span>
          <span class="solution-detail__time">{{ formatDateTime(solution.created_at) }}</span>
          <span v-if="solution.updated_at !== solution.created_at" class="solution-detail__time">
            {{ t('problems.solutions.editedAt', { time: formatDateTime(solution.updated_at) }) }}
          </span>
          <span class="solution-detail__spacer" />
          <n-button v-if="isOwner" size="tiny" secondary @click="edit">
            {{ t('action.edit') }}
          </n-button>
          <n-button v-if="isOwner" size="tiny" secondary type="error" @click="remove">
            {{ t('action.delete') }}
          </n-button>
          <n-button v-if="canReport" size="tiny" quaternary @click="reportVisible = true">
            {{ t('community.report.short') }}
          </n-button>
        </div>

        <div class="solution-detail__content">
          <MarkdownView :source="solution.content" />
        </div>

        <CommentSection target-type="solution" :target-id="solutionId" />
      </div>
    </n-spin>
    <div v-show="!loading && !solution" class="table-fill-empty solution-detail__empty">
      {{ t('common.loadFailed') }}
    </div>

    <ReportDialog v-model:show="reportVisible" target-type="solution" :target-id="solutionId" />
  </WorkbenchShell>
</template>

<style scoped>
.solution-detail {
  max-width: 860px;
  margin: 0 auto;
  padding-bottom: 24px;
}
.solution-detail__title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 4px 0 10px;
  font-size: 20px;
  font-weight: 700;
}
.solution-detail__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.solution-detail__author {
  font-weight: 600;
  color: var(--app-text);
}
.solution-detail__spacer {
  flex: 1;
}
.solution-detail__content {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--app-border);
}
.solution-detail__empty {
  color: var(--app-text-secondary);
}
</style>
