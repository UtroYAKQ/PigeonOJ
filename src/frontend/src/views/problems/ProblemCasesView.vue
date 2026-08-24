<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { getProblem, replaceSamples, replaceTestCases } from '@/api/problems'
import { message } from '@/utils/feedback'
import type { ProblemDetailEx, TestCaseDraft } from '@/types'
import TestCaseImporter from '@/components/problem/TestCaseImporter.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const saving = ref(false)
const loading = ref(false)
const problemId = String(route.params.id)

const cases = ref<TestCaseDraft[]>([])
/** 展示样例（problems.samples；仅展示与自测，不参与判题） */
const samples = ref<Array<{ input: string; output: string }>>([])

function addCase() {
  cases.value.push({
    name: String(cases.value.length + 1),
    input: '',
    expected_output: '',
    sort_order: cases.value.length + 1,
  })
}
function addSample() {
  if (samples.value.length >= 10) return
  samples.value.push({ input: '', output: '' })
}
function removeSample(index: number) {
  samples.value.splice(index, 1)
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

async function loadExisting() {
  loading.value = true
  try {
    const loaded: ProblemDetailEx = await getProblem(problemId)
    if (!loaded.can_manage) throw new Error(t('problems.create.noPermission'))
    if (loaded.test_cases?.length)
      cases.value = loaded.test_cases.map((item) => ({
        name: item.name ?? '',
        input: item.input ?? '',
        expected_output: item.expected_output ?? '',
        sort_order: item.sort_order,
      }))
    samples.value = (loaded.samples ?? []).map((item) => ({ input: item.input, output: item.output }))
    // 记录服务器端快照，保存时用于签名比对跳过无变化上传
    serverCases = loaded.test_cases ?? undefined
    serverSamples = samples.value.map((item) => ({ ...item }))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
    router.push('/admin/problems')
  } finally {
    loading.value = false
  }
}

/** 签名对比：内容未变化时不重复上传，避免无谓触发「需重新验题」 */
function caseSignature(list?: Array<{ name?: string | null; input: string; expected_output: string }>) {
  return JSON.stringify((list ?? []).map((item) => [item.name ?? '', item.input ?? '', item.expected_output ?? '']))
}
function sampleSignature(list?: Array<{ input: string; output: string }>) {
  return JSON.stringify((list ?? []).map((item) => [item.input ?? '', item.output ?? '']))
}

/** 服务器端当前内容快照（loadExisting 时记录） */
let serverCases: TestCaseDraft[] | undefined = undefined
let serverSamples: Array<{ input: string; output: string }> = []

/** 持久化样例 + 测试点；成功返回 true */
async function save(): Promise<boolean> {
  normalize()
  saving.value = true
  try {
    // 空白草稿行不提交（后端拒绝全空测试点）；内容与服务器一致时跳过上传
    const validCases = cases.value
      .filter((item) => item.input.trim() || item.expected_output.trim())
      .map((item, index) => ({ ...item, sort_order: index + 1 }))
    if (validCases.length && caseSignature(validCases) !== caseSignature(serverCases)) {
      await replaceTestCases(problemId, validCases)
      serverCases = validCases
    }
    const validSamples = samples.value.filter((item) => item.input.trim() || item.output.trim())
    if (sampleSignature(validSamples) !== sampleSignature(serverSamples)) {
      await replaceSamples(problemId, validSamples)
      serverSamples = validSamples.map((item) => ({ ...item }))
    }
    message.success(t('problems.create.saved'))
    return true
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
    return false
  } finally {
    saving.value = false
  }
}

function goNext() {
  // 进入验题页前至少要有一个非空正式测试点（发布门禁依赖判题）
  const hasCase = cases.value.some((item) => item.input.trim() || item.expected_output.trim())
  if (!hasCase) {
    message.error(t('problems.wizard.stepNeedCases'))
    return
  }
  void save().then((ok) => {
    if (ok) router.push(`/admin/problems/${problemId}/edit/verify`)
  })
}
function goPrev() {
  router.push(`/admin/problems/${problemId}/edit/statement`)
}
function cancelEdit() {
  router.push('/admin/problems')
}

onMounted(loadExisting)
</script>

<template>
  <div class="page-stack">
    <n-spin :show="loading">
      <n-card :bordered="false">
        <template #header>
          <div class="card-head">
            <span>{{ t('problems.wizard.cases') }}</span>
            <n-button size="small" quaternary @click="cancelEdit">{{ t('action.cancel') }}</n-button>
          </div>
        </template>

        <!-- 步骤指示：当前第 2 步 -->
        <n-steps :current="2" size="small" class="wizard-steps">
          <n-step :title="t('problems.wizard.basic')" />
          <n-step :title="t('problems.wizard.cases')" />
          <n-step :title="t('problems.wizard.verifyPublish')" />
        </n-steps>

        <div class="wizard-body">
          <!-- 展示样例：存 problems.samples，仅展示与自测，不参与判题 -->
          <div class="samples-section">
            <div class="samples-head">
              <h3 class="samples-title">{{ t('problems.detail.samples') }}</h3>
              <n-button size="small" :disabled="samples.length >= 10" @click="addSample">
                {{ t('problems.create.addSample') }}
              </n-button>
            </div>
            <div v-if="samples.length" class="test-cases">
              <div v-for="(sample, index) in samples" :key="index" class="test-case">
                <div class="case-top">
                  <span class="case-index">{{ index + 1 }}</span>
                  <n-button text type="error" size="small" @click="removeSample(index)">
                    {{ t('problems.create.removeCase') }}
                  </n-button>
                </div>
                <div class="case-content">
                  <n-input
                    v-model:value="sample.input"
                    type="textarea"
                    :rows="3"
                    :placeholder="t('problems.create.inputContent')"
                  />
                  <n-input
                    v-model:value="sample.output"
                    type="textarea"
                    :rows="3"
                    :placeholder="t('problems.create.outputContent')"
                  />
                </div>
              </div>
            </div>
            <n-empty v-else :description="t('problems.detail.noSamples')" size="small" />
          </div>

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
          </div>
          <n-empty v-else :description="t('problems.create.contentRequired')" />
        </div>

        <!-- 底部导航：下一步自动保存样例与测试点 -->
        <div class="wizard-footer">
          <n-button :disabled="saving" @click="goPrev">{{ t('problems.wizard.prev') }}</n-button>
          <div class="wizard-footer__spacer" />
          <n-button type="primary" :loading="saving" @click="goNext">{{
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
.wizard-body {
  min-height: 320px;
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
.samples-section {
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--app-border);
}
.samples-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.samples-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
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
  .case-content {
    grid-template-columns: 1fr;
  }
}
</style>
