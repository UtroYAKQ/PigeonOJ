<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { deleteProblemSpj, getProblem, getProblemSpj, getProblemTestCases, patchTestCases, replaceProblemSpj, replaceSamples } from '@/api/problems'
import { getTeamProblem } from '@/api/teams'
import { dialog, message } from '@/utils/feedback'
import type { ProblemDetail, ProblemTestCase, TestCaseDraft, TestCaseUpsertPayload } from '@/types'
import TestCaseImporter from '@/components/problem/TestCaseImporter.vue'
import WizardShell from '@/components/WizardShell.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const saving = ref(false)
const loading = ref(false)
const problemId = String(route.params.id)
/** 团队上下文：回读走团队端点（豁免题库可见性），步骤跳转回团队路由 */
const teamId = route.params.teamId ? String(route.params.teamId) : null
const isTeam = teamId !== null

const cases = ref<TestCaseDraft[]>([])
/** 展示样例（problems.samples；仅展示与自测，不参与判题；explanation 为选填样例解释） */
const samples = ref<Array<{ input: string; output: string; explanation: string }>>([])

/** SPJ 特判程序（docs/contracts/problems.md「SPJ 特判程序」）：
 * 编辑的是暂存集（验题通过后随 apply 晋升生效） */
const spjCode = ref('')
const spjSaving = ref(false)
/** 服务器端目标状态基线：null = 目标状态无特判程序 */
const spjBaseline = ref<string | null>(null)
const spjStaged = ref(false)
const spjDirty = computed(() => spjCode.value !== (spjBaseline.value ?? ''))

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
  samples.value.push({ input: '', output: '', explanation: '' })
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
    // 团队题目经团队上下文端点回读（题库裸路径按可见性拦截，docs/contracts/teams.md）
    const loaded: ProblemDetail = await (isTeam
      ? getTeamProblem(teamId!, problemId)
      : getProblem(problemId))
    if (!loaded.can_manage) throw new Error(t('problems.create.noPermission'))
    // 测试点走独立管理端点（详情不再携带）
    const caseList = await getProblemTestCases(problemId)
    if (caseList.cases.length)
      cases.value = caseList.cases.map((item) => ({
        id: item.id,
        name: item.name ?? '',
        input: item.input ?? '',
        expected_output: item.expected_output ?? '',
        sort_order: item.sort_order,
        staged: item.staged ?? false,
      }))
    samples.value = (loaded.samples ?? []).map((item) => ({
      input: item.input,
      output: item.output,
      explanation: item.explanation ?? '',
    }))
    // SPJ 目标状态回读（暂存优先；code=null 表示目标状态无特判程序）
    const spj = await getProblemSpj(problemId)
    spjCode.value = spj.code ?? ''
    spjBaseline.value = spj.code
    spjStaged.value = spj.staged
    // 记录服务器端基线快照，保存时按行 diff 只提交变化的测试点
    serverCases = caseList.cases ?? []
    serverSamples = samples.value.map((item) => ({ ...item }))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
    router.push(isTeam ? `/teams/${teamId}` : '/admin/problems')
  } finally {
    loading.value = false
  }
}

function sampleSignature(list?: Array<{ input: string; output: string; explanation?: string }>) {
  return JSON.stringify(
    (list ?? []).map((item) => [item.input ?? '', item.output ?? '', item.explanation ?? '']),
  )
}

/** 服务器端当前内容快照（loadExisting / 保存成功后刷新） */
let serverCases: ProblemTestCase[] = []
let serverSamples: Array<{ input: string; output: string; explanation: string }> = []

/** 行级 diff：新增（无 id）、内容/名称变化、位置变化、被移除的行 */
function diffCases(validCases: TestCaseDraft[]): {
  upserts: TestCaseUpsertPayload[]
  delete_ids: string[]
} {
  const baselineIndex = new Map(serverCases.map((c, index) => [c.id, index]))
  const upserts = validCases
    .map((row, index) => ({ row, index }))
    .filter(({ row, index }) => {
      if (!row.id) return true // 新增行
      const base = serverCases.find((c) => c.id === row.id)
      if (!base) return true
      return (
        (row.name || '') !== (base.name ?? '') ||
        row.input !== (base.input ?? '') ||
        row.expected_output !== (base.expected_output ?? '') ||
        baselineIndex.get(row.id) !== index
      )
    })
    .map(({ row, index }) => ({
      id: row.id ?? null,
      name: row.name,
      input: row.input,
      expected_output: row.expected_output,
      sort_order: index + 1,
    }))
  const keepIds = new Set(validCases.map((row) => row.id).filter(Boolean) as string[])
  const delete_ids = serverCases.filter((c) => !keepIds.has(c.id)).map((c) => c.id)
  return { upserts, delete_ids }
}

/** 持久化特判程序（按基线 diff 决定 PUT / DELETE；无改动跳过）；成功返回 true */
async function saveSpj(): Promise<boolean> {
  if (!spjDirty.value) return true
  spjSaving.value = true
  try {
    if (spjCode.value.trim()) {
      await replaceProblemSpj(problemId, spjCode.value)
      spjBaseline.value = spjCode.value
      spjStaged.value = true
      message.success(t('problems.create.spjSaved'))
    } else if (spjBaseline.value !== null) {
      await deleteProblemSpj(problemId)
      spjBaseline.value = null
      spjStaged.value = true
      message.success(t('problems.create.spjRemoved'))
    }
    return true
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
    return false
  } finally {
    spjSaving.value = false
  }
}

/** 移除特判程序：确认后清空并立即写暂存移除（apply 晋升后生效集才真正置空） */
function removeSpj() {
  dialog.warning({
    title: t('problems.create.spjRemove'),
    content: t('problems.create.spjRemoveConfirm'),
    positiveText: t('problems.create.spjRemove'),
    negativeText: t('action.cancel'),
    onPositiveClick: () => {
      spjCode.value = ''
      void saveSpj()
    },
  })
}

/** 持久化样例 + 测试点 + 特判程序；成功返回 true */
async function save(): Promise<boolean> {
  normalize()
  saving.value = true
  try {
    // 空白草稿行不提交（后端拒绝全空测试点）；按行对比只提交有变化的测试点
    const validCases = cases.value
      .filter((item) => item.input.trim() || item.expected_output.trim())
      .map((item, index) => ({ ...item, sort_order: index + 1 }))
    const { upserts, delete_ids } = diffCases(validCases)
    if (upserts.length || delete_ids.length) {
      const resp = await patchTestCases(problemId, { upserts, delete_ids })
      // 以服务器权威列表重置本地行与基线（新建行获得 id）
      cases.value = resp.cases.map((c) => ({
        id: c.id,
        name: c.name ?? '',
        input: c.input ?? '',
        expected_output: c.expected_output ?? '',
        sort_order: c.sort_order,
        staged: c.staged ?? false,
      }))
      normalize()
      serverCases = resp.cases.map((c) => ({ ...c }))
    }
    const validSamples = samples.value.filter((item) => item.input.trim() || item.output.trim())
    if (sampleSignature(validSamples) !== sampleSignature(serverSamples)) {
      await replaceSamples(problemId, validSamples)
      serverSamples = validSamples.map((item) => ({ ...item }))
    }
    const spjOk = await saveSpj()
    if (!spjOk) return false
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
    const target = isTeam
      ? `/teams/${teamId}/problems/${problemId}/edit/verify`
      : `/admin/problems/${problemId}/edit/verify`
    if (ok) router.push(target)
  })
}
function goPrev() {
  router.push(
    isTeam
      ? `/teams/${teamId}/problems/${problemId}/edit/statement`
      : `/admin/problems/${problemId}/edit/statement`,
  )
}
/** 保存并退出：持久化样例与测试点后返回来源列表 */
function saveAndExit() {
  void save().then((ok) => {
    if (ok) router.push(isTeam ? `/teams/${teamId}` : '/admin/problems')
  })
}

onMounted(loadExisting)
</script>

<template>
  <div class="page-stack">
    <n-spin :show="loading">
      <WizardShell :step="2" :title="t('problems.wizard.cases')">
        <template #actions>
          <n-button size="small" :disabled="saving" @click="goPrev">
            {{ t('problems.wizard.prev') }}
          </n-button>
          <n-button type="primary" size="small" :loading="saving" @click="goNext">
            {{ t('problems.wizard.next') }}
          </n-button>
          <n-button size="small" quaternary :disabled="saving" @click="saveAndExit">
            {{ t('problems.wizard.saveExit') }}
          </n-button>
        </template>

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
                  <span class="case-index case-index--accent">{{ index + 1 }}</span>
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
                <n-input
                  v-model:value="sample.explanation"
                  type="textarea"
                  :rows="2"
                  class="sample-explanation-input"
                  :placeholder="t('problems.create.explanationPlaceholder')"
                />
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
                <n-tag v-if="item.staged" size="small" type="warning" round :bordered="false">
                  {{ t('problems.create.stagedBadge') }}
                </n-tag>
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

          <!-- SPJ 特判程序：C++17 单文件 checker，写暂存集（验题通过后晋升生效） -->
          <div class="spj-section">
            <div class="samples-head">
              <h3 class="samples-title">{{ t('problems.create.spjTitle') }}</h3>
              <div class="spj-actions">
                <n-tag v-if="spjStaged" size="small" type="warning" round :bordered="false">
                  {{ t('problems.create.stagedBadge') }}
                </n-tag>
                <n-tag v-if="spjDirty" size="small" round :bordered="false">
                  {{ t('problems.create.spjModified') }}
                </n-tag>
                <n-button
                  size="small"
                  type="primary"
                  secondary
                  :disabled="!spjDirty"
                  :loading="spjSaving"
                  @click="saveSpj"
                >
                  {{ t('problems.create.spjSave') }}
                </n-button>
                <n-button
                  v-if="spjBaseline !== null"
                  size="small"
                  type="error"
                  secondary
                  :disabled="spjSaving"
                  @click="removeSpj"
                >
                  {{ t('problems.create.spjRemove') }}
                </n-button>
              </div>
            </div>
            <p class="spj-desc">{{ t('problems.create.spjDesc') }}</p>
            <n-input
              v-model:value="spjCode"
              type="textarea"
              :rows="10"
              class="spj-editor"
              :placeholder="t('problems.create.spjPlaceholder')"
            />
          </div>
        </div>
      </WizardShell>
    </n-spin>
  </div>
</template>

<style scoped>
.wizard-body {
  min-height: 320px;
}
.cases-toolbar {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-bottom: 16px;
}
.test-cases {
  display: grid;
  gap: 12px;
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
/* 序号 chip：测试点用中性底，样例用主题色底（--accent），一眼区分两类卡片 */
.case-index {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border: 1px solid var(--app-border);
  border-radius: 4px;
  color: var(--app-text-secondary);
  background: var(--app-card-bg);
  font-size: 12px;
  font-weight: 600;
}
.case-index--accent {
  border-color: transparent;
  color: var(--app-primary);
  background: color-mix(in srgb, var(--app-primary) 9%, transparent);
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
/* 样例解释：通栏选填输入（Markdown），留空 = 该组无解释 */
.sample-explanation-input {
  margin-top: 12px;
}
/* SPJ 特判程序区块：与样例区分隔，等宽编辑 */
.spj-section {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--app-border);
}
.spj-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.spj-desc {
  margin: 4px 0 10px;
  color: var(--app-text-secondary);
  font-size: 12px;
}
.spj-editor :deep(textarea),
.spj-editor :deep(.n-input__textarea-el) {
  font-family: ui-monospace, SFMono-Regular, Consolas, 'Courier New', monospace;
  font-size: 13px;
}
@media (max-width: 760px) {
  .case-content {
    grid-template-columns: 1fr;
  }
}
</style>
