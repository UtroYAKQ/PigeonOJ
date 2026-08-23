<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { uploadSpj } from '@/api/files'
import { createProblem, getProblem, replaceTestCases, updateProblem } from '@/api/problems'
import type { ProblemDetailEx } from '@/api/problems'
import type { TestCaseDraft } from '@/api/types'
import TestCaseImporter from '@/components/problem/TestCaseImporter.vue'

const route = useRoute(); const router = useRouter(); const { t } = useI18n()
const isEdit = computed(() => Boolean(route.params.id))
const saving = ref(false); const loading = ref(false); const uploadingSpj = ref(false)
const problemId = ref<string | null>(null)
const problemStatus = ref('draft')
const spjInput = ref<HTMLInputElement>()

const form = reactive({
  title: '',
  description: '',
  input_description: '',
  output_description: '',
  solution: '',
  difficulty: 'easy',
  visibility: 'public',
  time_limit_ms: 1000,
  memory_limit_mb: 256,
  spj: false,
  spj_code: '' as string | null,
})
const cases = ref<TestCaseDraft[]>([{ name: '1', input: '', expected_output: '', is_sample: false, score: 100, sort_order: 1 }])

function addCase() {
  cases.value.push({ name: String(cases.value.length + 1), input: '', expected_output: '', is_sample: false, score: 0, sort_order: cases.value.length + 1 })
}
function removeCase(index: number) { cases.value.splice(index, 1) }
function importCases(items: TestCaseDraft[]) { cases.value = items; normalize() }
function normalize() {
  cases.value.forEach((item, index) => {
    item.sort_order = index + 1
    if (!item.name) item.name = String(index + 1)
  })
}

async function chooseSpj(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  uploadingSpj.value = true
  try {
    const result = await uploadSpj(file)
    form.spj = true
    form.spj_code = result.oss_id
    ElMessage.success(t('problems.create.spjUploaded'))
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : t('problems.create.spjUploadFailed'))
  } finally {
    uploadingSpj.value = false
    if (spjInput.value) spjInput.value.value = ''
  }
}

function payload() {
  return {
    title: form.title,
    description: form.description,
    input_description: form.input_description || null,
    output_description: form.output_description || null,
    solution: form.solution || null,
    difficulty: form.difficulty,
    visibility: form.visibility,
    time_limit_ms: form.time_limit_ms,
    memory_limit_mb: form.memory_limit_mb,
    spj: form.spj,
    spj_code: form.spj ? form.spj_code : null,
  }
}

async function loadExisting() {
  if (!isEdit.value) return
  loading.value = true
  try {
    const detail: ProblemDetailEx = await getProblem(String(route.params.id))
    if (!detail.can_manage) throw new Error(t('problems.create.noPermission'))
    problemId.value = detail.id
    problemStatus.value = detail.status
    Object.assign(form, {
      title: detail.title,
      description: detail.description,
      input_description: detail.input_description ?? '',
      output_description: detail.output_description ?? '',
      solution: detail.solution ?? '',
      difficulty: detail.difficulty,
      visibility: detail.visibility ?? 'public',
      time_limit_ms: detail.time_limit_ms,
      memory_limit_mb: detail.memory_limit_mb,
      spj: detail.spj,
      // spj_code 为 MinIO ossId，不回显内容，仅保留引用避免误清空
      spj_code: null,
    })
    if (detail.test_cases?.length) cases.value = detail.test_cases.map(item => ({
      name: item.name ?? '',
      input: item.input ?? '',
      expected_output: item.expected_output ?? '',
      is_sample: item.is_sample,
      score: item.score,
      sort_order: item.sort_order,
    }))
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
    router.push('/problems')
  } finally { loading.value = false }
}

async function save() {
  normalize()
  if (!form.title || !form.description) { ElMessage.error(t('problems.create.baseInfoRequired')); return }
  if (cases.value.some(item => !item.input && !item.expected_output)) { ElMessage.error(t('problems.create.contentRequired')); return }
  saving.value = true
  try {
    let targetId = problemId.value
    if (!targetId) {
      const created = await createProblem(payload() as Parameters<typeof createProblem>[0])
      targetId = created.id
      problemId.value = targetId
    } else {
      await updateProblem(targetId, payload())
    }
    await replaceTestCases(targetId, cases.value)
    ElMessage.success(isEdit.value ? t('problems.create.saved') : t('problems.create.draftCreated'))
    router.push(`/problems/${targetId}`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally { saving.value = false }
}

onMounted(loadExisting)
</script>
<template>
  <div v-loading="loading" class="problem-create">
    <header class="page-heading">
      <div>
        <p class="page-heading__eyebrow">{{ t('nav.problems') }}</p>
        <h1>{{ isEdit ? t('problems.create.editTitle') : t('problems.create.title') }}</h1>
        <p>{{ t('problems.create.description') }}</p>
      </div>
      <div class="page-heading__actions">
        <el-button @click="router.push('/problems')">{{ t('action.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ t('problems.create.saveDraft') }}</el-button>
      </div>
    </header>

    <div class="problem-create__grid">
      <el-card shadow="never" class="base-card">
        <template #header>{{ t('problems.create.baseInfo') }}</template>
        <el-form label-position="top">
          <el-form-item :label="t('problems.create.name')"><el-input v-model="form.title" size="large"/></el-form-item>
          <el-form-item :label="t('problems.create.statement')"><el-input v-model="form.description" type="textarea" :rows="10"/></el-form-item>
          <div class="form-grid">
            <el-form-item :label="t('problems.create.inputDescription')"><el-input v-model="form.input_description" type="textarea" :rows="4"/></el-form-item>
            <el-form-item :label="t('problems.create.outputDescription')"><el-input v-model="form.output_description" type="textarea" :rows="4"/></el-form-item>
          </div>
          <details class="solution-details">
            <summary>{{ t('problems.create.solutionToggle') }}</summary>
            <el-form-item :label="t('problems.create.solution')" class="solution-field"><el-input v-model="form.solution" type="textarea" :rows="5"/></el-form-item>
          </details>
          <div class="form-grid">
            <el-form-item :label="t('problems.list.difficulty')">
              <el-select v-model="form.difficulty">
                <el-option label="Easy" value="easy"/><el-option label="Medium" value="medium"/><el-option label="Hard" value="hard"/>
              </el-select>
            </el-form-item>
            <el-form-item :label="t('problems.create.visibility')">
              <el-select v-model="form.visibility">
                <el-option :label="t('problems.create.visibilityPublic')" value="public"/>
                <el-option :label="t('problems.create.visibilityPrivate')" value="private"/>
              </el-select>
            </el-form-item>
            <el-form-item :label="t('problems.create.timeLimit')"><el-input-number v-model="form.time_limit_ms" :min="1"/></el-form-item>
            <el-form-item :label="t('problems.create.memoryLimit')"><el-input-number v-model="form.memory_limit_mb" :min="16"/></el-form-item>
          </div>
          <el-form-item><el-checkbox v-model="form.spj">{{ t('problems.create.useSpj') }}</el-checkbox></el-form-item>
          <template v-if="form.spj">
            <el-form-item :label="t('problems.create.checkerFile')">
              <div class="spj-row">
                <el-button :loading="uploadingSpj" @click="spjInput?.click()">{{ t('problems.create.uploadChecker') }}</el-button>
                <span v-if="form.spj_code" class="spj-ref">{{ form.spj_code }}</span>
              </div>
              <input ref="spjInput" type="file" accept=".cpp,.cc,.cxx" hidden @change="chooseSpj">
              <p class="form-hint">{{ t('problems.create.checkerHint') }}</p>
            </el-form-item>
          </template>
        </el-form>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="case-header">
            <span>{{ t('problems.create.testCases') }}</span>
            <div class="case-actions">
              <TestCaseImporter @imported="importCases"/>
              <el-button @click="addCase">{{ t('problems.create.addCase') }}</el-button>
            </div>
          </div>
        </template>
        <div v-if="cases.length" class="test-cases">
          <div v-for="(item, index) in cases" :key="item.name + index" class="test-case">
            <div class="test-case__top">
              <span class="test-case__index">{{ index + 1 }}</span>
              <el-input v-model="item.name" :placeholder="t('problems.create.caseName')" class="test-case__name"/>
              <el-checkbox v-model="item.is_sample">{{ t('problems.create.sampleCase') }}</el-checkbox>
              <el-input-number v-if="!item.is_sample" v-model="item.score" :min="0" :max="100" size="small"/>
              <el-button link type="danger" @click="removeCase(index)">{{ t('problems.create.removeCase') }}</el-button>
            </div>
            <div class="case-content">
              <el-input v-model="item.input" type="textarea" :rows="3" :placeholder="t('problems.create.inputContent')"/>
              <el-input v-model="item.expected_output" type="textarea" :rows="3" :placeholder="t('problems.create.outputContent')"/>
            </div>
          </div>
          <p class="form-hint">{{ t('problems.create.storageHint') }}</p>
        </div>
        <el-empty v-else :description="t('problems.create.contentRequired')" :image-size="60"/>
      </el-card>
    </div>
  </div>
</template>
<style scoped>.problem-create{display:grid;gap:20px;max-width:1180px}.page-heading{display:flex;align-items:end;justify-content:space-between;gap:16px}.page-heading__eyebrow{margin:0 0 6px;color:var(--el-color-primary);font-size:11px;font-weight:800;letter-spacing:.1em;text-transform:uppercase}.page-heading h1{margin:0;font-size:26px;letter-spacing:-.035em}.page-heading p:not(.page-heading__eyebrow){margin:8px 0 0;color:var(--app-text-muted);font-size:13px}.page-heading__actions,.case-actions{display:flex;gap:10px}.problem-create__grid{display:grid;grid-template-columns:minmax(320px,1fr) minmax(360px,1fr);gap:18px;align-items:start}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.form-hint{margin:8px 0 0;color:var(--app-text-muted);font-size:12px;line-height:1.5}.solution-details{margin-bottom:18px}.solution-details summary{cursor:pointer;color:var(--app-text-muted);font-size:13px;margin-bottom:12px}.spj-row{display:flex;align-items:center;gap:10px}.spj-ref{color:var(--app-text-muted);font-size:12px;word-break:break-all}.case-header,.test-case__top{display:flex;align-items:center;justify-content:space-between;gap:10px}.test-cases{display:grid;gap:14px}.test-case{padding:14px;border:1px solid var(--app-border);border-radius:11px;background:var(--app-surface-muted)}.test-case__top{justify-content:flex-start}.test-case__index{display:grid;place-items:center;width:24px;height:24px;border-radius:50%;color:var(--el-color-primary);background:var(--el-color-primary-light-8);font-size:12px;font-weight:750}.test-case__name{max-width:160px}.case-content{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}@media(max-width:900px){.problem-create__grid{grid-template-columns:1fr}}@media(max-width:760px){.page-heading,.case-header,.test-case__top{align-items:start;flex-direction:column}.form-grid,.case-content{grid-template-columns:1fr}}</style>
