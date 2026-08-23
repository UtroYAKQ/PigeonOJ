<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { getSubmission } from '@/api/judge'
import type { Submission } from '@/types'

const route = useRoute(); const router = useRouter(); const { t } = useI18n()
const submission = ref<Submission | null>(null)
const loading = ref(false); const showCode = ref(true)
/** 自动刷新上限：2s × 150 = 5 分钟，避免无退避的无限轮询 */
const MAX_POLLS = 150
const pollCount = ref(0)
let timer: number | undefined

const isRunning = computed(() => submission.value?.status === 'pending' || submission.value?.status === 'judging')
/** 达到轮询上限仍未出结果 → 停止自动刷新，提示手动刷新 */
const pollingStopped = computed(() => isRunning.value && pollCount.value >= MAX_POLLS)
const resultIcon = computed(() => {
  const s = submission.value?.status
  return s === 'accepted' ? 'success' : isRunning.value ? 'info' : 'error'
})
const statusLabel = computed(() => t(`problems.status.${submission.value?.status ?? 'pending'}`))

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    submission.value = await getSubmission(String(route.params.id))
    if (isRunning.value && !pollingStopped.value) {
      timer = window.setTimeout(() => load(true), 2000)
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : t('problems.submission.loadFailed'))
  } finally {
    if (!silent) loading.value = false
  }
}

onMounted(() => { pollCount.value = 1; load() })
onUnmounted(() => { if (timer) window.clearTimeout(timer) })
</script>

<template>
  <div class="submission-page page-stack">
    <el-card shadow="never" v-loading="loading">
      <template v-if="submission">
        <div class="result-head" :class="{ running: isRunning }">
          <span class="result-status" :data-status="submission.status">{{ statusLabel }}</span>
          <span class="result-lang">{{ submission.language }}</span>
          <span v-if="submission.submit_type === 'verify'" class="result-verify">{{ t('problems.submission.verifyType') }}</span>
          <el-button
            v-if="isRunning"
            class="result-refresh"
            size="small"
            :icon="Refresh"
            :aria-label="t('action.refresh')"
            @click="pollCount = 0; load()"
          >{{ t('action.refresh') }}</el-button>
          <el-button
            v-else
            link
            class="result-back"
            @click="submission?.problem_id ? router.push(`/problems/${submission.problem_id}`) : router.push('/problems/list')"
          >{{ submission?.problem_id ? t('problems.submission.backToProblem') : t('problems.submission.back') }}</el-button>
        </div>

        <el-alert v-if="pollingStopped" type="info" :closable="false" show-icon class="poll-stopped">
          {{ t('problems.submission.stillJudging') }}
        </el-alert>

        <div class="submission-stats">
          <div><span>{{ t('problems.submission.score') }}</span><strong>{{ submission.score }}</strong></div>
          <div><span>{{ t('problems.submission.time') }}</span><strong>{{ submission.time_used_ms ?? 0 }} <small>ms</small></strong></div>
          <div><span>{{ t('problems.submission.memory') }}</span><strong>{{ submission.memory_used_kb ?? 0 }} <small>KB</small></strong></div>
        </div>

        <el-alert v-if="submission.error_message" type="error" :closable="false" show-icon class="compile-error">
          <template #title>{{ t('problems.submission.errorMessage') }}</template>
          <pre class="error-box">{{ submission.error_message }}</pre>
        </el-alert>

        <div class="code-toggle">
          <el-button link type="primary" @click="showCode = !showCode">{{ showCode ? t('problems.submission.hideCode') : t('problems.submission.showCode') }}</el-button>
        </div>
        <pre v-if="showCode" class="result-box code-box">{{ submission.code }}</pre>

        <template v-if="submission.cases && submission.cases.length">
          <h3 class="section-title cases-title">{{ t('problems.submission.caseResults') }}</h3>
          <el-table :data="submission.cases" size="small">
            <el-table-column prop="case_name" label="#" min-width="90"/>
            <el-table-column :label="t('problems.detail.status')" min-width="170">
              <template #default="{ row }">
                <el-tag size="small" :type="row.status === 'accepted' ? 'success' : row.status === 'wrong_answer' ? 'warning' : 'danger'">{{ t(`problems.status.${row.status}`) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('problems.submission.time')" width="110">
              <template #default="{ row }">{{ row.time_used_ms ?? '-' }} ms</template>
            </el-table-column>
            <el-table-column :label="t('problems.submission.memory')" width="110">
              <template #default="{ row }">{{ row.memory_used_kb ?? '-' }} KB</template>
            </el-table-column>
            <el-table-column prop="score" :label="t('problems.submission.score')" width="80"/>
          </el-table>
        </template>
      </template>
      <el-result v-else-if="!loading" icon="info" :title="t('common.noData')"/>
    </el-card>
  </div>
</template>

<style scoped>
/* 卡片水平居中 */
.submission-page { max-width: 900px; margin: 0 auto; }

.result-head { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.result-status { font-size: 20px; font-weight: 750; color: var(--el-color-success); }
.result-status[data-status="pending"], .result-status[data-status="judging"] { color: var(--el-color-info); animation: pulse 1.2s ease-in-out infinite; }
.result-status:not([data-status="accepted"]):not([data-status="pending"]):not([data-status="judging"]) { color: var(--el-color-danger); }
@keyframes pulse { 50% { opacity: .45; } }
.result-lang, .result-verify { padding: 2px 10px; border-radius: 999px; border: 1px solid var(--app-border); font-size: 12px; color: var(--app-text-muted); }
/* 返回按钮始终位于行尾：单个 margin-left:auto 把右侧动作整体推到最右 */
.result-back { margin-left: auto; }

.poll-stopped { margin-bottom: 14px; }

.submission-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 10px 0 16px; }
.submission-stats > div { display: grid; gap: 8px; padding: 18px; border: 1px solid var(--app-border); border-radius: 12px; background: var(--app-surface-muted); }
.submission-stats span { color: var(--app-text-muted); font-size: 12px; font-weight: 650; }
.submission-stats strong { font-size: 22px; }
.submission-stats small { color: var(--app-text-muted); font-size: 12px; font-weight: 500; }

.compile-error { margin-bottom: 16px; }
.error-box { margin: 8px 0 0; white-space: pre-wrap; word-break: break-all; font-family: var(--el-font-family-mono); font-size: 12px; }

.code-toggle { margin-top: 16px; }
.code-box { margin-top: 0; }
.cases-title { margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--app-border); }

@media (max-width: 600px) {
  .submission-stats { grid-template-columns: 1fr; }
}
</style>
