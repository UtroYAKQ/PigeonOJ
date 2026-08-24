<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { createProblem, getProblem, replaceTestCases, updateProblem } from '@/api/problems'
import { message } from '@/utils/feedback'
import type { ProblemDetailEx, TestCaseDraft } from '@/types'
import TestCaseImporter from '@/components/problem/TestCaseImporter.vue'
import VerifyPublishPanel from '@/components/problem/VerifyPublishPanel.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const isEdit = computed(() => Boolean(route.params.id))
const saving = ref(false)
const loading = ref(false)
const problemId = ref<string | null>(null)
const problemStatus = ref('draft')
const showSolution = ref(false)
/** 完整详情（含验题状态），供「验题与发布」步骤使用 */
const detail = ref<ProblemDetailEx | null>(null)

// ---- 分步向导 ----
const step = ref(0)
const stepItems = computed(() => [
  { title: t('problems.wizard.basic') },
  { title: t('problems.wizard.cases') },
  { title: t('problems.wizard.verifyPublish') },
])
function validateStep(index: number): boolean {
  if (index === 0) {
    if (!form.title.trim() || !form.description.trim()) {
      message.error(t('problems.wizard.stepNeedBasic'))
      return false
    }
    return true
  }
  if (index === 1) {
    if (!cases.value.length || cases.value.some((item) => !item.input && !item.expected_output)) {
      message.error(t('problems.wizard.stepNeedCases'))
      return false
    }
    return true
  }
  return true
}
function nextStep() {
  if (validateStep(step.value)) step.value = Math.min(2, step.value + 1)
}
function prevStep() {
  step.value = Math.max(0, step.value - 1)
}

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
})
const cases = ref<TestCaseDraft[]>([
  { name: '1', input: '', expected_output: '', is_sample: false, sort_order: 1 },
])

function addCase() {
  cases.value.push({
    name: String(cases.value.length + 1),
    input: '',
    expected_output: '',
    is_sample: false,
    sort_order: cases.value.length + 1,
  })
}
function removeCase(index: number) {
  cases.value.splice(index, 1)
}
function importCases(items: TestCaseDraft[]) {
  cases.value = items
  normalize()
}
function normalize() {
  cases.value.forEach((item, index) => {
    item.sort_order = index + 1
    if (!item.name) item.name = String(index + 1)
  })
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
  }
}

async function loadExisting() {
  if (!problemId.value) return
  loading.value = true
  try {
    const loaded: ProblemDetailEx = await getProblem(String(problemId.value))
    if (!loaded.can_manage) throw new Error(t('problems.create.noPermission'))
    detail.value = loaded
    problemStatus.value = loaded.status
    Object.assign(form, {
      title: loaded.title,
      description: loaded.description,
      input_description: loaded.input_description ?? '',
      output_description: loaded.output_description ?? '',
      solution: loaded.solution ?? '',
      difficulty: loaded.difficulty,
      visibility: loaded.visibility ?? 'public',
      time_limit_ms: loaded.time_limit_ms,
      memory_limit_mb: loaded.memory_limit_mb,
    })
    if (loaded.test_cases?.length)
      cases.value = loaded.test_cases.map((item) => ({
        name: item.name ?? '',
        input: item.input ?? '',
        expected_output: item.expected_output ?? '',
        is_sample: item.is_sample,
        sort_order: item.sort_order,
      }))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
    router.push('/admin/problems')
  } finally {
    loading.value = false
  }
}

async function save() {
  normalize()
  if (!form.title || !form.description) {
    message.error(t('problems.create.baseInfoRequired'))
    return
  }
  if (cases.value.some((item) => !item.input && !item.expected_output)) {
    message.error(t('problems.create.contentRequired'))
    return
  }
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
    message.success(isEdit.value ? t('problems.create.saved') : t('problems.create.draftCreated'))
    // 重载详情刷新验题状态（案例变更会触发「需重新验题」）；新建后直接跳到验题步骤
    await loadExisting()
    if (step.value === 0) step.value = 1
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function loadRouteProblem() {
  if (isEdit.value) problemId.value = String(route.params.id)
  await loadExisting()
}
onMounted(loadRouteProblem)

function cancelEdit() {
  router.push('/admin/problems')
}
function onPublished() {
  // 发布成功后回到管理工作台（前台详情页不承载管理动线）
  router.push('/admin/problems')
}

const difficultyOptions = computed(() => [
  { label: t('problems.difficulty.easy'), value: 'easy' },
  { label: t('problems.difficulty.medium'), value: 'medium' },
  { label: t('problems.difficulty.hard'), value: 'hard' },
])
const visibilityOptions = computed(() => [
  { label: t('problems.create.visibilityPublic'), value: 'public' },
  { label: t('problems.create.visibilityPrivate'), value: 'private' },
])
</script>

<template>
  <div class="page-stack">
    <n-spin :show="loading">
      <n-card :bordered="false">
        <template #header>
          <div class="card-head">
            <span>{{ isEdit ? t('problems.create.editTitle') : t('problems.create.title') }}</span>
            <n-button size="small" quaternary @click="cancelEdit">{{ t('action.cancel') }}</n-button>
          </div>
        </template>

        <!-- 步骤条 -->
        <n-steps :current="step + 1" size="small" class="wizard-steps">
          <n-step v-for="item in stepItems" :key="item.title" :title="item.title" />
        </n-steps>

        <!-- 第一步：基础信息与题面 -->
        <div v-if="step === 0" class="wizard-body">
          <n-form label-placement="top">
            <n-form-item :label="t('problems.create.name')">
              <n-input v-model:value="form.title" size="large" />
            </n-form-item>
            <n-form-item :label="t('problems.create.statement')">
              <n-input v-model:value="form.description" type="textarea" :rows="10" />
            </n-form-item>
            <div class="form-grid">
              <n-form-item :label="t('problems.create.inputDescription')">
                <n-input v-model:value="form.input_description" type="textarea" :rows="4" />
              </n-form-item>
              <n-form-item :label="t('problems.create.outputDescription')">
                <n-input v-model:value="form.output_description" type="textarea" :rows="4" />
              </n-form-item>
            </div>
            <n-collapse-transition :show="showSolution">
              <n-form-item :label="t('problems.create.solution')" class="solution-field">
                <n-input v-model:value="form.solution" type="textarea" :rows="5" />
              </n-form-item>
            </n-collapse-transition>
            <n-button
              text
              size="small"
              type="primary"
              class="solution-toggle"
              @click="showSolution = !showSolution"
            >
              {{ t('problems.create.solutionToggle') }}
            </n-button>
            <div class="form-grid">
              <n-form-item :label="t('problems.list.difficulty')">
                <n-select v-model:value="form.difficulty" :options="difficultyOptions" />
              </n-form-item>
              <n-form-item :label="t('problems.create.visibility')">
                <n-select v-model:value="form.visibility" :options="visibilityOptions" />
              </n-form-item>
              <n-form-item :label="t('problems.create.timeLimit')">
                <n-input-number v-model:value="form.time_limit_ms" :min="1" class="w-full" />
              </n-form-item>
              <n-form-item :label="t('problems.create.memoryLimit')">
                <n-input-number v-model:value="form.memory_limit_mb" :min="16" class="w-full" />
              </n-form-item>
            </div>
          </n-form>
        </div>

        <!-- 第二步：测试点与样例 -->
        <div v-else-if="step === 1" class="wizard-body">
          <div class="cases-toolbar">
            <TestCaseImporter @imported="importCases" />
            <n-button size="small" @click="addCase">{{ t('problems.create.addCase') }}</n-button>
          </div>
          <div v-if="cases.length" class="test-cases">
            <div v-for="(item, index) in cases" :key="item.name + index" class="test-case">
              <div class="case-top">
                <span class="case-index">{{ index + 1 }}</span>
                <n-input
                  v-model:value="item.name"
                  class="case-name"
                  size="small"
                  :placeholder="t('problems.create.caseName')"
                />
                <n-checkbox v-model:checked="item.is_sample" size="small">
                  {{ t('problems.create.sampleCase') }}
                </n-checkbox>
                <n-button text type="error" size="small" @click="removeCase(index)">
                  {{ t('problems.create.removeCase') }}
                </n-button>
              </div>
              <div class="case-content">
                <n-input
                  v-model:value="item.input"
                  type="textarea"
                  :rows="3"
                  :placeholder="t('problems.create.inputContent')"
                />
                <n-input
                  v-model:value="item.expected_output"
                  type="textarea"
                  :rows="3"
                  :placeholder="t('problems.create.outputContent')"
                />
              </div>
            </div>
            <p class="form-hint">{{ t('problems.create.storageHint') }}</p>
          </div>
          <n-empty v-else :description="t('problems.create.contentRequired')" />
        </div>

        <!-- 第三步：验题与发布 -->
        <div v-else class="wizard-body">
          <VerifyPublishPanel
            v-if="detail"
            :problem="detail"
            @refresh="loadExisting"
            @published="onPublished"
          />
          <n-empty v-else :description="t('problems.wizard.stepNeedBasic')" />
        </div>

        <!-- 步骤导航 / 保存 -->
        <div class="wizard-footer">
          <n-button v-if="step > 0" @click="prevStep">{{ t('problems.wizard.prev') }}</n-button>
          <div class="wizard-footer__spacer" />
          <n-button :loading="saving" @click="save">{{
            problemId ? t('action.save') : t('problems.create.saveDraft')
          }}</n-button>
          <n-button v-if="step < 2" type="primary" @click="nextStep">{{
            t('problems.wizard.next')
          }}</n-button>
        </div>
      </n-card>
    </n-spin>
  </div>
</template>

<style scoped>
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}
.wizard-steps {
  margin-bottom: 20px;
}
.wizard-body {
  min-height: 320px;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}
.solution-toggle {
  margin-bottom: 16px;
}
.w-full {
  width: 100%;
}
.cases-toolbar {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-bottom: 14px;
}
.test-cases {
  display: grid;
  gap: 14px;
}
.test-case {
  padding: 12px;
  border: 1px solid var(--app-border);
  border-radius: 6px;
  background: var(--app-muted-bg);
}
.case-top {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
}
.case-index {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  color: var(--app-primary);
  background: rgba(244, 81, 30, 0.09);
  font-size: 12px;
  font-weight: 600;
}
.case-name {
  max-width: 160px;
}
.case-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 12px;
}
.wizard-footer {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--app-border);
}
.wizard-footer__spacer {
  flex: 1;
}
@media (max-width: 760px) {
  .form-grid,
  .case-content {
    grid-template-columns: 1fr;
  }
}
</style>
