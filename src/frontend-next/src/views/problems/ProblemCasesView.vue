<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import { getOrgProblem } from '@/api/orgs'
import {
  deleteProblemSpj,
  getProblem,
  getProblemSpj,
  getProblemTestCases,
  patchTestCases,
  replaceProblemSpj,
  replaceSamples,
} from '@/api/problems'
import { getTeamProblem } from '@/api/teams'
import CodeEditor from '@/components/common/CodeEditor.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import { Button } from '@/components/ui/button'
import { confirmDialog, message } from '@/utils/feedback'
import type { ProblemDetail, ProblemTestCase, TestCaseDraft, TestCaseUpsertPayload } from '@/types'
import SamplesSection from '@/views/problems/components/SamplesSection.vue'
import TestCasesSection from '@/views/problems/components/TestCasesSection.vue'
import WizardSteps from '@/views/problems/components/WizardSteps.vue'

interface SampleDraft {
  input: string
  output: string
  explanation: string
}

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const saving = ref(false)
const loading = ref(false)
const problemId = String(route.params.id ?? route.params.problemId)
/** 团队 / 组织上下文：回读走上下文端点，步骤跳转回上下文路由 */
const teamId = route.params.teamId ? String(route.params.teamId) : null
const isTeam = teamId !== null
const orgId = route.params.orgId ? String(route.params.orgId) : null
const isOrg = orgId !== null

const cases = ref<TestCaseDraft[]>([])
/** 展示样例（problems.samples；仅展示与自测，不参与判题；explanation 为选填样例解释） */
const samples = ref<SampleDraft[]>([])

/** SPJ 特判程序：编辑的是暂存集（验题通过后随 apply 晋升生效） */
const spjCode = ref('')
const spjSaving = ref(false)
/** 服务器端目标状态基线：null = 目标状态无特判程序 */
const spjBaseline = ref<string | null>(null)
const spjStaged = ref(false)
const spjDirty = computed(() => spjCode.value !== (spjBaseline.value ?? ''))

/** 服务器端当前内容快照（loadExisting / 保存成功后刷新） */
let serverCases: ProblemTestCase[] = []
let serverSamples: SampleDraft[] = []

function normalize(): void {
  cases.value.forEach((item, index) => {
    item.sort_order = index + 1
    if (!item.name) item.name = String(index + 1)
  })
}

function toDraft(item: ProblemTestCase): TestCaseDraft {
  return {
    id: item.id,
    name: item.name ?? '',
    input: item.input ?? '',
    expected_output: item.expected_output ?? '',
    sort_order: item.sort_order,
    staged: item.staged ?? false,
  }
}

async function loadExisting(): Promise<void> {
  loading.value = true
  try {
    // 团队题目经团队上下文端点回读（题库裸路径按可见性拦截）
    const loaded: ProblemDetail = await (isOrg
      ? getOrgProblem(orgId!, problemId)
      : isTeam
        ? getTeamProblem(teamId!, problemId)
        : getProblem(problemId))
    if (!loaded.can_manage) throw new Error(t('problems.create.noPermission'))
    // 测试点走独立管理端点（详情不再携带）
    const caseList = await getProblemTestCases(problemId)
    if (caseList.cases.length) cases.value = caseList.cases.map(toDraft)
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
    void router.push(isOrg ? `/orgs/${orgId}` : isTeam ? `/teams/${teamId}` : '/admin/problems')
  } finally {
    loading.value = false
  }
}

function sampleSignature(list?: SampleDraft[]): string {
  return JSON.stringify(
    (list ?? []).map((item) => [item.input ?? '', item.output ?? '', item.explanation ?? '']),
  )
}

/** 行级 diff：新增（无 id）、内容/名称变化、位置变化、被移除的行 */
function diffCases(validCases: TestCaseDraft[]): {
  upserts: TestCaseUpsertPayload[]
  delete_ids: string[]
} {
  const baselineIndex = new Map(serverCases.map((item, index) => [item.id, index]))
  const upserts = validCases
    .map((row, index) => ({ row, index }))
    .filter(({ row, index }) => {
      if (!row.id) return true // 新增行
      const base = serverCases.find((item) => item.id === row.id)
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
  const delete_ids = serverCases.filter((item) => !keepIds.has(item.id)).map((item) => item.id)
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
async function removeSpj(): Promise<void> {
  const ok = await confirmDialog({
    title: t('problems.create.spjRemove'),
    content: t('problems.create.spjRemoveConfirm'),
    positiveText: t('problems.create.spjRemove'),
    negativeText: t('action.cancel'),
    danger: true,
  })
  if (!ok) return
  spjCode.value = ''
  await saveSpj()
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
      cases.value = resp.cases.map(toDraft)
      normalize()
      serverCases = resp.cases.map((item) => ({ ...item }))
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

function goNext(): void {
  // 进入验题页前至少要有一个非空正式测试点（发布门禁依赖判题）
  const hasCase = cases.value.some((item) => item.input.trim() || item.expected_output.trim())
  if (!hasCase) {
    message.error(t('problems.wizard.stepNeedCases'))
    return
  }
  void save().then((ok) => {
    const target = isOrg
      ? `/orgs/${orgId}/problems/${problemId}/edit/verify`
      : isTeam
        ? `/teams/${teamId}/problems/${problemId}/edit/verify`
        : `/admin/problems/${problemId}/edit/verify`
    if (ok) void router.push(target)
  })
}

function goPrev(): void {
  void router.push(
    isOrg
      ? `/orgs/${orgId}/problems/${problemId}/edit/statement`
      : isTeam
        ? `/teams/${teamId}/problems/${problemId}/edit/statement`
        : `/admin/problems/${problemId}/edit/statement`,
  )
}

/** 保存并退出：持久化样例与测试点后返回来源列表 */
function saveAndExit(): void {
  void save().then((ok) => {
    if (ok) {
      void router.push(isOrg ? `/orgs/${orgId}` : isTeam ? `/teams/${teamId}` : '/admin/problems')
    }
  })
}

onMounted(loadExisting)
</script>

<template>
  <div class="mx-auto w-full max-w-[1200px] px-4 pb-12 pt-4 sm:px-6">
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div class="min-w-0">
        <h1 class="text-xl font-semibold leading-tight tracking-tight">
          {{ t('problems.wizard.cases') }}
        </h1>
        <div class="mt-2">
          <WizardSteps :current="2" />
        </div>
      </div>
    </header>

    <div class="my-5 h-px bg-border" role="separator" />

    <div v-if="loading" class="grid h-[320px] place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <div v-else class="space-y-8">
      <!-- 展示样例：存 problems.samples，仅展示与自测，不参与判题 -->
      <SamplesSection v-model="samples" />

      <div class="h-px bg-border" role="separator" />
      <TestCasesSection v-model="cases" />

      <!-- SPJ 特判程序：C++17 单文件 checker，写暂存集（验题通过后晋升生效） -->
      <section>
        <div class="h-px bg-border" role="separator" />
        <div class="flex flex-wrap items-center justify-between gap-2 pt-8">
          <div class="flex items-center gap-2">
            <h2 class="text-lg font-medium">{{ t('problems.create.spjTitle') }}</h2>
            <ToneBadge v-if="spjStaged" tone="warning" :label="t('problems.create.stagedBadge')" />
            <ToneBadge v-if="spjDirty" tone="info" :label="t('problems.create.spjModified')" />
          </div>
          <div class="flex items-center gap-2">
            <Button variant="outline" :disabled="!spjDirty || spjSaving" @click="saveSpj">
              <Loader2 v-if="spjSaving" class="size-4 animate-spin" />
              {{ t('problems.create.spjSave') }}
            </Button>
            <Button
              v-if="spjBaseline !== null"
              variant="ghost"
              class="text-destructive hover:text-destructive"
              :disabled="spjSaving"
              @click="removeSpj"
            >
              {{ t('problems.create.spjRemove') }}
            </Button>
          </div>
        </div>
        <p class="mt-1 text-sm leading-5 text-muted-foreground">
          {{ t('problems.create.spjDesc') }}
        </p>
        <div class="mt-5 h-[320px]">
          <CodeEditor v-model="spjCode" language="cpp17" />
        </div>
      </section>

      <div class="flex flex-wrap justify-start gap-2 pt-2">
        <Button :disabled="saving || loading" @click="goNext">
          <Loader2 v-if="saving" class="size-4 animate-spin" />
          {{ t('problems.wizard.next') }}
        </Button>
        <Button variant="outline" :disabled="saving || loading" @click="goPrev">
          {{ t('problems.wizard.prev') }}
        </Button>
        <Button variant="ghost" :disabled="saving || loading" @click="saveAndExit">
          {{ t('problems.wizard.saveExit') }}
        </Button>
      </div>
    </div>
  </div>
</template>
