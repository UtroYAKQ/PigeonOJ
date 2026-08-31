<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NButton } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import { useTimeoutFn } from '@vueuse/core'
import { getSubmission } from '@/api/judge'
import { message } from '@/utils/feedback'
import RefreshButton from '@/components/RefreshButton.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { Submission, SubmissionCaseResult } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const submission = ref<Submission | null>(null)
const loading = ref(false)
const showCode = ref(true)
/** 自动刷新上限：2s × 150 = 5 分钟，避免无退避的无限轮询 */
const MAX_POLLS = 150
const POLL_INTERVAL_MS = 2000
const pollCount = ref(0)

// 链式延时轮询：上一次响应返回后再等 2s 才发起下一次（与原 setTimeout 语义一致，卸载自动取消）
const scheduleNextPoll = useTimeoutFn(() => void load(true), POLL_INTERVAL_MS, {
  immediate: false,
})

const isRunning = computed(
  () => submission.value?.status === 'pending' || submission.value?.status === 'judging',
)
/** 达到轮询上限仍未出结果 → 停止自动刷新，提示手动刷新 */
const pollingStopped = computed(() => isRunning.value && pollCount.value >= MAX_POLLS)
const statusLabel = computed(() => t(`problems.status.${submission.value?.status ?? 'pending'}`))

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    submission.value = await getSubmission(String(route.params.id))
    if (isRunning.value && !pollingStopped.value) {
      pollCount.value += 1
      scheduleNextPoll.start()
    }
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.submission.loadFailed'))
  } finally {
    if (!silent) loading.value = false
  }
}

/** 手动刷新：重置轮询计数并立即拉取 */
function refreshNow() {
  pollCount.value = 0
  void load()
}
/** 站内是否有来路（vue-router 在 history.state.back 记录上一跳） */
const canGoBack = computed(() => {
  const back = router.options.history.state.back
  return typeof back === 'string' && back.length > 0 && back !== route.fullPath
})
const backLabel = computed(() => {
  if (canGoBack.value) return t('problems.submission.back')
  return submission.value?.problem_id
    ? t('problems.submission.backToProblem')
    : t('problems.submission.back')
})

/** 返回：有来路时原路返回（验题工作台 / 提交列表等）；直接进入则回题目详情 */
function back() {
  if (canGoBack.value) {
    router.back()
    return
  }
  if (submission.value?.problem_id) router.push(`/problems/${submission.value.problem_id}`)
  else router.push('/problems/list')
}

onMounted(() => {
  load()
})

const caseColumns = computed<DataTableColumns<SubmissionCaseResult>>(() => [
  { title: '#', key: 'case_name', minWidth: 90 },
  {
    title: t('problems.detail.status'),
    key: 'status',
    minWidth: 170,
    render: (row) => h(StatusTag, { status: row.status }),
  },
  {
    title: t('problems.submission.time'),
    key: 'time',
    width: 110,
    render: (row) => `${row.time_used_ms ?? '-'} ms`,
  },
  {
    title: t('problems.submission.memory'),
    key: 'memory',
    width: 110,
    render: (row) => `${row.memory_used_kb ?? '-'} KB`,
  },
  {
    title: t('problems.submission.score'),
    key: 'score',
    width: 80,
    render: (row) => row.score ?? '-',
  },
])
</script>

<template>
  <div class="page-stack submission-page">
    <n-card :bordered="false">
      <n-spin :show="loading">
        <template v-if="submission">
          <n-alert v-if="pollingStopped" type="info" class="poll-stopped">
            {{ t('problems.submission.stillJudging') }}
          </n-alert>

          <div class="result-head">
            <span class="result-status" :data-status="submission.status">{{ statusLabel }}</span>
            <span class="result-lang">{{ submission.language }}</span>
            <span v-if="submission.submit_type === 'verify'" class="result-verify">{{
              t('problems.submission.verifyType')
            }}</span>
            <RefreshButton v-if="isRunning" :loading="loading" :aria-label="t('action.refresh')" @click="refreshNow" />
            <n-button text type="primary" class="result-back" @click="back">
              {{ backLabel }}
            </n-button>
          </div>

          <n-alert v-if="submission.restricted" type="warning" class="restricted-notice">
            {{ t('problems.submission.restrictedNotice') }}
          </n-alert>

          <div class="submission-stats" :class="{ 'submission-stats--two': submission.score === null }">
            <div v-if="submission.score !== null" class="stat-box">
              <span>{{ t('problems.submission.score') }}</span>
              <strong>{{ submission.score }}</strong>
            </div>
            <div class="stat-box">
              <span>{{ t('problems.submission.time') }}</span>
              <strong>{{ submission.time_used_ms ?? 0 }} <small>ms</small></strong>
            </div>
            <div class="stat-box">
              <span>{{ t('problems.submission.memory') }}</span>
              <strong>{{ submission.memory_used_kb ?? 0 }} <small>KB</small></strong>
            </div>
          </div>

          <n-alert v-if="submission.error_message" type="error" class="compile-error">
            {{ t('problems.submission.errorMessage') }}
            <pre class="error-box">{{ submission.error_message }}</pre>
          </n-alert>

          <div class="code-toggle">
            <n-button text type="primary" @click="showCode = !showCode">{{
              showCode ? t('problems.submission.hideCode') : t('problems.submission.showCode')
            }}</n-button>
          </div>
          <pre v-if="showCode" class="result-box code-box">{{ submission.code }}</pre>

          <template v-if="submission.cases && submission.cases.length">
            <h3 class="section-title cases-title">{{ t('problems.submission.caseResults') }}</h3>
            <n-data-table size="small" :columns="caseColumns" :data="submission.cases" />
          </template>
        </template>
        <n-empty
          v-else-if="!loading"
          :description="t('common.noData')"
          class="empty-state"
          size="large"
        >
          <template #extra>
            <NButton size="small" @click="back"> {{ backLabel }} </NButton>
          </template>
        </n-empty>
      </n-spin>
    </n-card>
  </div>
</template>

<style scoped>
/* 详情/结果型页面：卡片水平居中（docs/frontend.md 纵向分区） */
.submission-page {
  max-width: 900px;
  margin: 0 auto;
}
.result-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}
.result-status {
  font-size: 20px;
  font-weight: 700;
  color: #18a058;
}
.result-status[data-status='pending'],
.result-status[data-status='judging'] {
  color: #909399;
  animation: pulse 1.2s ease-in-out infinite;
}
.result-status:not([data-status='accepted']):not([data-status='pending']):not(
    [data-status='judging']
  ) {
  color: #d03050;
}
@keyframes pulse {
  50% {
    opacity: 0.45;
  }
}
.result-lang,
.result-verify {
  padding: 2px 8px;
  border-radius: 3px;
  border: 1px solid var(--app-border);
  font-size: 12px;
  color: var(--app-text-secondary);
}
.result-back {
  margin-left: auto;
}
.poll-stopped {
  margin-bottom: 14px;
}
.restricted-notice {
  margin-bottom: 14px;
}
.submission-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin: 10px 0 16px;
}
/* ACM 限分模式：隐藏得分格后时间 / 内存两格均分 */
.submission-stats--two {
  grid-template-columns: repeat(2, 1fr);
}
.stat-box {
  display: grid;
  gap: 8px;
  padding: 16px;
  border: 1px solid var(--app-border);
  border-radius: 6px;
  background: var(--app-muted-bg);
}
.stat-box span {
  color: var(--app-text-secondary);
  font-size: 12px;
  font-weight: 500;
}
.stat-box strong {
  font-size: 22px;
}
.stat-box small {
  color: var(--app-text-secondary);
  font-size: 12px;
  font-weight: 500;
}
.compile-error {
  margin-bottom: 16px;
}
.error-box {
  margin: 8px 0 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: ui-monospace, SFMono-Regular, Consolas, 'Courier New', monospace;
  font-size: 12px;
}
.code-toggle {
  margin-top: 16px;
}
.code-box {
  margin-top: 8px;
}
.cases-title {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--app-border);
}
.empty-state {
  padding: 40px 0;
}
@media (max-width: 600px) {
  .submission-stats {
    grid-template-columns: 1fr;
  }
}
</style>
