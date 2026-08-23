<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { getSubmission } from '@/api/judge'
import type { Submission } from '@/api/types'

const route = useRoute(); const router = useRouter(); const { t } = useI18n()
const submission = ref<Submission | null>(null)
const loading = ref(false); const showCode = ref(false)
let timer: number | undefined

const isRunning = computed(() => submission.value?.status === 'pending' || submission.value?.status === 'judging')
const resultIcon = computed(() => {
  const s = submission.value?.status
  return s === 'accepted' ? 'success' : isRunning.value ? 'info' : 'error'
})
const statusLabel = computed(() => t(`problems.status.${submission.value?.status ?? 'pending'}`))

async function load() {
  loading.value = true
  try {
    submission.value = await getSubmission(String(route.params.id))
    if (isRunning.value) timer = window.setTimeout(load, 2000)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : t('problems.submission.loadFailed'))
  } finally { loading.value = false }
}
onMounted(load)
onUnmounted(() => { if (timer) window.clearTimeout(timer) })
</script>
<template>
  <div class="submission-page">
    <header class="page-heading">
      <div>
        <p class="page-heading__eyebrow">{{ t('nav.problems') }}</p>
        <h1>{{ t('problems.submission.title') }}</h1>
        <p>{{ t('problems.submission.id') }}：{{ route.params.id }}</p>
      </div>
      <el-button v-if="submission?.problem_id" @click="router.push(`/problems/${submission.problem_id}`)">{{ t('problems.submission.backToProblem') }}</el-button>
      <el-button v-else @click="router.push('/problems/list')">{{ t('problems.submission.back') }}</el-button>
    </header>

    <el-card shadow="never" v-loading="loading">
      <template v-if="submission">
        <div class="result-head" :class="{ running: isRunning }">
          <span class="result-status" :data-status="submission.status">{{ statusLabel }}</span>
          <span class="result-lang">{{ submission.language }}</span>
          <span v-if="submission.submit_type === 'verify'" class="result-verify">{{ t('problems.submission.verifyType') }}</span>
        </div>

        <div class="submission-stats">
          <div><span>{{ t('problems.submission.score') }}</span><strong>{{ submission.score }}</strong></div>
          <div><span>{{ t('problems.submission.time') }}</span><strong>{{ submission.time_used_ms ?? 0 }} <small>ms</small></strong></div>
          <div><span>{{ t('problems.submission.memory') }}</span><strong>{{ submission.memory_used_kb ?? 0 }} <small>KB</small></strong></div>
        </div>

        <el-alert v-if="submission.error_message" type="error" :closable="false" show-icon class="compile-error">
          <template #title>{{ t('problems.submission.errorMessage') }}</template>
          <pre class="error-box">{{ submission.error_message }}</pre>
        </el-alert>

        <template v-if="submission.cases && submission.cases.length">
          <h3 class="section-title">{{ t('problems.submission.caseResults') }}</h3>
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

        <div class="code-toggle">
          <el-button link type="primary" @click="showCode = !showCode">{{ showCode ? t('problems.submission.hideCode') : t('problems.submission.showCode') }}</el-button>
        </div>
        <pre v-if="showCode" class="result-box code-box">{{ submission.code }}</pre>
      </template>
      <el-result v-else-if="!loading" icon="info" :title="t('common.noData')"/>
    </el-card>
  </div>
</template>
<style scoped>.submission-page{display:grid;gap:20px;max-width:900px}.page-heading{display:flex;align-items:end;justify-content:space-between;gap:16px}.page-heading__eyebrow{margin:0 0 6px;color:var(--el-color-primary);font-size:11px;font-weight:800;letter-spacing:.1em;text-transform:uppercase}.page-heading h1{margin:0;font-size:26px;letter-spacing:-.035em}.page-heading p:not(.page-heading__eyebrow){margin:8px 0 0;color:var(--app-text-muted);font-size:13px}.result-head{display:flex;align-items:center;gap:12px;margin-bottom:14px}.result-status{font-size:20px;font-weight:750;color:var(--el-color-success)}.result-status[data-status="accepted"]{color:var(--el-color-success)}.result-status[data-status="pending"],.result-status[data-status="judging"]{color:var(--el-color-info);animation:pulse 1.2s ease-in-out infinite}.result-status:not([data-status="accepted"]):not([data-status="pending"]):not([data-status="judging"]){color:var(--el-color-danger)}@keyframes pulse{50%{opacity:.45}}.result-lang,.result-verify{padding:2px 10px;border-radius:999px;border:1px solid var(--app-border);font-size:12px;color:var(--app-text-muted)}.submission-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:10px 0 16px}.submission-stats>div{display:grid;gap:8px;padding:18px;border:1px solid var(--app-border);border-radius:12px;background:var(--app-surface-muted)}.submission-stats span{color:var(--app-text-muted);font-size:12px;font-weight:650}.submission-stats strong{font-size:22px}.submission-stats small{color:var(--app-text-muted);font-size:12px;font-weight:500}.compile-error{margin-bottom:16px}.error-box{margin:8px 0 0;white-space:pre-wrap;word-break:break-all;font-family:var(--el-font-family-mono);font-size:12px}.section-title{margin:4px 0 10px;font-size:14px}.result-box{max-height:360px;overflow:auto;margin:10px 0 0;white-space:pre-wrap;word-break:break-all;border:1px solid var(--app-border);border-radius:9px;background:var(--app-surface-muted);padding:12px;font-family:var(--el-font-family-mono);font-size:12px}.code-toggle{margin-top:14px}@media(max-width:600px){.page-heading{align-items:start;flex-direction:column}.submission-stats{grid-template-columns:1fr}}</style>
