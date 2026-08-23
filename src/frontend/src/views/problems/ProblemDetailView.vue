<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { createSubmission, getSubmission, listSubmissions } from '@/api/judge'
import { archiveProblem, getProblem, publishProblem } from '@/api/problems'
import CodeEditor from '@/components/CodeEditor.vue'
import type { ProblemDetailEx } from '@/api/problems'
import type { ProblemLanguage, Submission } from '@/api/types'

const route = useRoute(); const router = useRouter(); const { t } = useI18n()
const problem = ref<ProblemDetailEx | null>(null)
const loading = ref(false); const submitting = ref(false)
const publishing = ref(false); const archiving = ref(false)
const language = ref<ProblemLanguage>('cpp17')
const mySubmissions = ref<Submission[]>([])
const code = ref('#include <iostream>\nusing namespace std;\n\nint main() {\n    return 0;\n}\n')
const templates: Record<ProblemLanguage, string> = {
  cpp17: code.value,
  'python3.12': 'import sys\n\nfor line in sys.stdin:\n    print(line.rstrip())\n',
  java21: 'import java.io.*;\n\npublic class Main {\n    public static void main(String[] args) throws Exception {\n    }\n}\n',
}

const statusTagType = computed(() => {
  const s = problem.value?.status
  return s === 'published' ? 'success' : s === 'archived' ? 'info' : 'warning'
})

function changeLanguage(value: ProblemLanguage) { language.value = value; code.value = templates[value] }

async function copyText(text: string) {
  try { await navigator.clipboard.writeText(text); ElMessage.success(t('problems.detail.copied')) } catch { ElMessage.error(t('common.operationFailed')) }
}

async function load() {
  loading.value = true
  try {
    problem.value = await getProblem(String(route.params.id))
    await loadMySubmissions()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
  } finally { loading.value = false }
}
async function loadMySubmissions() {
  try {
    const result = await listSubmissions({ problem_id: String(route.params.id), page_size: 5 })
    mySubmissions.value = result.items
  } catch { /* 未登录等场景静默 */ }
}

async function submit() {
  if (!problem.value) return
  submitting.value = true
  try {
    const result = await createSubmission({ problem_id: problem.value.id, language: language.value, code: code.value })
    router.push(`/problems/${problem.value.id}/submissions/${result.submission_id}`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : t('problems.detail.submitFailed'))
  } finally { submitting.value = false }
}

async function doPublish() {
  if (!problem.value) return
  publishing.value = true
  try {
    const updated = await publishProblem(problem.value.id)
    problem.value = { ...problem.value, ...updated }
    ElMessage.success(t('problems.detail.publishSuccess'))
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : t('common.operationFailed')) } finally { publishing.value = false }
}
async function doArchive() {
  if (!problem.value) return
  archiving.value = true
  try {
    const updated = await archiveProblem(problem.value.id)
    problem.value = { ...problem.value, ...updated }
    ElMessage.success(t('problems.detail.archiveSuccess'))
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : t('common.operationFailed')) } finally { archiving.value = false }
}

onMounted(load)
</script>
<template>
  <div v-loading="loading" class="problem-detail">
    <header v-if="problem" class="problem-detail__heading">
      <div>
        <p class="problem-detail__eyebrow">{{ t('nav.problems') }} / #{{ problem.id.slice(0, 8) }}</p>
        <h1>{{ problem.title }}</h1>
        <div class="problem-detail__meta">
          <el-tag size="small" :type="problem.difficulty === 'hard' ? 'danger' : problem.difficulty === 'medium' ? 'warning' : 'success'" effect="light">{{ problem.difficulty }}</el-tag>
          <el-tag v-if="problem.status !== 'published'" size="small" :type="statusTagType">{{ problem.status }}</el-tag>
          <span>{{ problem.time_limit_ms }} ms</span>
          <span>{{ problem.memory_limit_mb }} MB</span>
          <el-tag size="small">{{ problem.spj ? 'SPJ' : t('problems.detail.standard') }}</el-tag>
          <el-tag v-for="tag in problem.tags" :key="tag" size="small" effect="plain" class="problem-detail__tag">{{ tag }}</el-tag>
        </div>
      </div>
      <div class="problem-detail__actions">
        <template v-if="problem.can_manage">
          <el-button @click="router.push(`/problems/${problem.id}/edit`)">{{ t('action.edit') }}</el-button>
          <el-button v-if="problem.status === 'draft'" type="primary" :loading="publishing" @click="doPublish">{{ t('problems.detail.publish') }}</el-button>
          <el-button v-if="problem.status !== 'archived'" type="danger" plain :loading="archiving" @click="doArchive">{{ t('problems.detail.archive') }}</el-button>
        </template>
        <el-button @click="router.push('/problems/list')">{{ t('problems.submission.back') }}</el-button>
      </div>
    </header>

    <div v-if="problem" class="problem-detail__grid">
      <div class="problem-detail__left">
        <el-card shadow="never">
          <template #header>{{ t('problems.detail.title') }}</template>
          <div class="statement">{{ problem.description }}</div>
        </el-card>
        <el-card v-if="problem.input_description" shadow="never">
          <template #header>{{ t('problems.detail.inputDescription') }}</template>
          <div class="statement">{{ problem.input_description }}</div>
        </el-card>
        <el-card v-if="problem.output_description" shadow="never">
          <template #header>{{ t('problems.detail.outputDescription') }}</template>
          <div class="statement">{{ problem.output_description }}</div>
        </el-card>
        <el-card v-if="problem.solution" shadow="never">
          <template #header>{{ t('problems.detail.solution') }}</template>
          <div class="statement">{{ problem.solution }}</div>
        </el-card>

        <el-card shadow="never">
          <template #header>{{ t('problems.detail.samples') }}</template>
          <div v-if="problem.samples.length" class="samples">
            <div v-for="(sample, index) in problem.samples" :key="sample.id ?? index" class="sample-block">
              <div class="sample-block__head">
                <strong>#{{ index + 1 }} {{ sample.name }}</strong>
                <div class="sample-block__actions">
                  <el-button link @click="copyText(sample.input)">{{ t('problems.detail.copyInput') }}</el-button>
                </div>
              </div>
              <div class="sample-grid2">
                <div><p class="sample-label">{{ t('problems.detail.stdin') }}</p><pre class="result-box">{{ sample.input || t('problems.detail.noOutput') }}</pre></div>
                <div><p class="sample-label">{{ t('problems.submission.expectedOutput') }}</p><pre class="result-box">{{ sample.output || t('problems.detail.noOutput') }}</pre></div>
              </div>
            </div>
            <p class="form-hint">{{ t('problems.detail.sampleHint') }}</p>
          </div>
          <el-empty v-else :description="t('problems.detail.noSamples')" :image-size="60"/>
        </el-card>
      </div>

      <div class="problem-detail__right">
        <el-card shadow="never" class="editor-card">
          <div class="editor-toolbar">
            <el-select :model-value="language" class="editor-toolbar__language" @change="changeLanguage">
              <el-option label="C++17" value="cpp17"/>
              <el-option label="Python 3.12" value="python3.12"/>
              <el-option label="Java 21" value="java21"/>
            </el-select>
            <div class="editor-toolbar__actions">
              <el-button type="primary" :loading="submitting" @click="submit">{{ t('problems.detail.submit') }}</el-button>
            </div>
          </div>
          <CodeEditor v-model="code" :language="language"/>
        </el-card>

        <el-card shadow="never">
          <template #header>{{ t('problems.detail.mySubmissions') }}</template>
          <el-table v-if="mySubmissions.length" :data="mySubmissions" size="small" class="sub-table"
            @row-click="(row: Submission) => router.push(`/problems/${route.params.id}/submissions/${row.id}`)">
            <el-table-column prop="status" :label="t('problems.detail.status')" min-width="150">
              <template #default="{ row }"><el-tag size="small" :type="row.status === 'accepted' ? 'success' : ['pending', 'judging'].includes(row.status) ? 'info' : 'danger'">{{ row.status }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="score" :label="t('problems.submission.score')" width="80"/>
            <el-table-column :label="t('problems.submission.time')" width="110">
              <template #default="{ row }">{{ row.time_used_ms ?? '-' }} ms</template>
            </el-table-column>
            <el-table-column prop="language" :label="t('problems.detail.language')" width="120"/>
          </el-table>
          <el-empty v-else :description="t('problems.detail.noSubmissions')" :image-size="60"/>
        </el-card>
      </div>
    </div>
  </div>
</template>
<style scoped>.problem-detail{display:grid;gap:20px}.problem-detail__heading{display:flex;align-items:end;justify-content:space-between;gap:16px}.problem-detail__eyebrow{margin:0 0 7px;color:var(--el-color-primary);font-size:11px;font-weight:800;letter-spacing:.1em;text-transform:uppercase}.problem-detail h1{margin:0;font-size:28px;letter-spacing:-.04em}.problem-detail__meta{display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin-top:10px;color:var(--app-text-muted);font-size:12px}.problem-detail__actions{display:flex;gap:8px}.problem-detail__grid{display:grid;grid-template-columns:minmax(300px,.9fr) minmax(420px,1.1fr);gap:18px;align-items:start}.problem-detail__left,.problem-detail__right{display:grid;gap:18px;min-width:0}.statement{white-space:pre-wrap;line-height:1.8}.editor-card{min-width:0}.editor-toolbar{display:flex;justify-content:space-between;gap:12px;margin-bottom:14px}.editor-toolbar__language{width:150px}.editor-toolbar__actions{display:flex;gap:8px}.samples{display:grid;gap:16px}.sample-block{border:1px solid var(--app-border);border-radius:11px;padding:12px;background:var(--app-surface-muted)}.sample-block__head{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}.sample-block__actions{display:flex;gap:4px}.sample-grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.sample-label{margin:0 0 6px;font-size:12px;color:var(--app-text-muted);font-weight:650}.sample-grid,.output-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.output-grid{margin-top:14px}.output-grid strong{display:block;margin-bottom:7px;font-size:13px}.result-box{min-height:64px;max-height:240px;overflow:auto;margin:0;white-space:pre-wrap;word-break:break-all;border:1px solid var(--app-border);border-radius:9px;background:var(--app-surface-muted);padding:10px 12px;font-family:var(--el-font-family-mono);font-size:12px}.sample-result-alert{margin-top:4px}.sub-table :deep(.el-table__row){cursor:pointer}.form-hint{margin:10px 0 0;color:var(--app-text-muted);font-size:12px;line-height:1.5}@media(max-width:900px){.problem-detail__grid{grid-template-columns:1fr}}@media(max-width:600px){.problem-detail__heading{align-items:start;flex-direction:column}.editor-toolbar{align-items:stretch;flex-direction:column}.editor-toolbar__language{width:100%}.editor-toolbar__actions .el-button{flex:1}.sample-grid,.sample-grid2,.output-grid{grid-template-columns:1fr}}</style>
