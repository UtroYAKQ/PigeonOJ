<script setup lang="ts">
/**
 * 评测结果总览（H4 收敛）：题目提交 / 题目管理提交 / 比赛提交 三份近重复页面
 * （轮询、状态、统计、代码、测点表、样式）抽出本组件渲染，数据与轮询经
 * useSubmissionDetail 由各页面持有（每上下文选独立端点）。
 * 顶部返回按钮文案 / 动作由父级经 backLabel + @back 提供（各上下文路由动线不同）。
 */
import { computed, h, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { DataTableColumns } from 'naive-ui'

import RefreshButton from '@/components/RefreshButton.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { Submission, SubmissionCaseResult } from '@/types'

const { t } = useI18n()
const showCode = ref(true)
const emit = defineEmits<{ back: []; refresh: [] }>()

const props = defineProps<{
  submission: Submission | null
  loading: boolean
  pollingStopped: boolean
  statusLabel: string
  /** ACM 二值计分（AC=满分否则 0）不展示为 IOI 分数格 / 分数列 */
  showScoreBox: boolean
  backLabel: string
}>()

const caseColumns = computed<DataTableColumns<SubmissionCaseResult>>(() => {
  // ACM：单测试点不计分（短路执行），分数列仅 IOI / 练习展示
  const cols: DataTableColumns<SubmissionCaseResult> = [
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
  ]
  if (props.showScoreBox) {
    cols.push({
      title: t('problems.submission.score'),
      key: 'score',
      width: 80,
      render: (row) => row.score ?? '-',
    })
  }
  return cols
})
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
            <RefreshButton
              :loading="loading"
              :aria-label="t('action.refresh')"
              @click="emit('refresh')"
            />
            <n-button text type="primary" class="result-back" @click="emit('back')">
              {{ backLabel }}
            </n-button>
          </div>

          <div
            class="submission-stats"
            :class="{ 'submission-stats--two': !showScoreBox || submission.score === null }"
          >
            <!-- ACM 二值分（AC=满分否则 0）或暂无得分不展示分数格 -->
            <div v-if="showScoreBox && submission.score !== null" class="stat-box">
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
            <n-button size="small" @click="emit('back')">
              {{ backLabel }}
            </n-button>
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
.submission-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin: 10px 0 16px;
}
/* ACM 限分模式 / 暂无得分：隐藏分数格后时间 / 内存两格均分 */
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