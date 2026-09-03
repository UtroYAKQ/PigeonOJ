<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { DataTableColumns } from 'naive-ui'

import { createSubmission, listSubmissions } from '@/api/judge'
import { getProblem } from '@/api/problems'
import { createProblemSetSubmission, getProblemSetProblem } from '@/api/problemSets'
import { createContestSubmission, getContestProblem } from '@/api/contests'
import { useCodeDraft } from '@/composables/useCodeDraft'
import { useSelfTest } from '@/composables/useSelfTest'
import { dialog, message } from '@/utils/feedback'
import StatusTag from '@/components/StatusTag.vue'
import ProblemWorkbench from '@/components/problem/ProblemWorkbench.vue'
import type { ProblemDetail, ProblemLanguage, Submission } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const problem = ref<ProblemDetail | null>(null)
const submitting = ref(false)
const subsVisible = ref(false)
const language = ref<ProblemLanguage>('cpp17')
const mySubmissions = ref<Submission[]>([])

/** 题目 id：题库路由取 params.id；题单 / 比赛上下文路由取 params.problemId */
const problemId = computed(() => String(route.params.problemId ?? route.params.id))
/** 上下文标识（同一组件复用于 题库 / 题单 / 比赛 三种上下文，取参与链接随上下文切换） */
const context = computed<'problems' | 'problem-sets' | 'contests'>(() =>
  route.params.cid ? 'contests' : route.params.setId ? 'problem-sets' : 'problems',
)
const contextId = computed(() =>
  context.value === 'contests'
    ? String(route.params.cid)
    : context.value === 'problem-sets'
      ? String(route.params.setId)
      : '',
)
/** 评测结果路由基路径：上下文内保持不跳出（评测结果页同构复用） */
const submissionsBase = computed(() => {
  if (context.value === 'contests') {
    return `/contests/${contextId.value}/problems/${problemId.value}`
  }
  if (context.value === 'problem-sets') {
    return `/problem-sets/${contextId.value}/problems/${problemId.value}`
  }
  return `/problems/${problemId.value}`
})

const code = ref('')

// 代码本地草稿：进入恢复、编辑防抖保存、切换语言分语言存档（提交/切页返回不丢）
const { restore: restoreDraft } = useCodeDraft({
  problemId: () => problemId.value,
  code,
  language,
})

// 用户自测：控制台状态在 composable 内（docs/contracts/judge.md「用户自测」）
const {
  selfTestInput,
  selfTesting,
  selfTestResult,
  runSelfTest: doSelfTest,
} = useSelfTest(() => problemId.value)

async function load() {
  try {
    // 统一入口：各上下文走本模块详情端点（归属 / 窗口校验），题库走题库端点
    problem.value =
      context.value === 'contests'
        ? await getContestProblem(contextId.value, problemId.value)
        : context.value === 'problem-sets'
          ? await getProblemSetProblem(contextId.value, problemId.value)
          : await getProblem(problemId.value)
    await loadMySubmissions()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
  }
}
async function loadMySubmissions() {
  try {
    const result = await listSubmissions({ problem_id: problemId.value, page_size: 5 })
    mySubmissions.value = result.items
  } catch {
    /* 未登录等场景静默 */
  }
}

function openSubmission(row: Submission) {
  subsVisible.value = false
  router.push(`${submissionsBase.value}/submissions/${row.id}`)
}

async function submit() {
  if (!problem.value || submitting.value) return
  if (!code.value.trim()) {
    message.warning(t('problems.detail.codeRequired'))
    return
  }
  dialog.warning({
    title: t('problems.detail.submit'),
    content: t('problems.detail.submitConfirm'),
    positiveText: t('problems.detail.submit'),
    negativeText: t('action.cancel'),
    onPositiveClick: async () => {
      const current = problem.value
      if (!current) return
      submitting.value = true
      try {
        // 统一入口：各上下文走本模块交题端点（题单：归属校验；比赛：窗口校验，赛后自动补题）
        let result: { submission_id: string; status: string }
        if (context.value === 'contests') {
          result = await createContestSubmission(contextId.value, current.id, {
            language: language.value,
            code: code.value,
          })
        } else if (context.value === 'problem-sets') {
          result = await createProblemSetSubmission(contextId.value, current.id, {
            language: language.value,
            code: code.value,
          })
        } else {
          result = await createSubmission({
            problem_id: current.id,
            language: language.value,
            code: code.value,
          })
        }
        router.push(`${submissionsBase.value}/submissions/${result.submission_id}`)
      } catch (error) {
        message.error(error instanceof Error ? error.message : t('problems.detail.submitFailed'))
      } finally {
        submitting.value = false
      }
    },
  })
}

async function runSelfTest() {
  if (!problem.value) return
  await doSelfTest({ language: language.value, code: code.value })
}

onMounted(() => {
  restoreDraft()
  void load()
})

const submissionColumns = computed<DataTableColumns<Submission>>(() => [
  {
    title: t('problems.detail.status'),
    key: 'status',
    minWidth: 150,
    render: (row) => h(StatusTag, { status: row.status }),
  },
  {
    title: t('problems.submission.score'),
    key: 'score',
    width: 80,
    render: (row) => row.score ?? '-',
  },
  {
    title: t('problems.submission.time'),
    key: 'time',
    width: 110,
    render: (row) => `${row.time_used_ms ?? '-'} ms`,
  },
  { title: t('problems.detail.language'), key: 'language', width: 120 },
])
</script>

<template>
  <div class="problem-detail">
    <!-- 双栏工作台大组件：左题面 + 右编辑器/自测控制台；按钮行为由本页注入 -->
    <ProblemWorkbench
      v-if="problem"
      v-model:code="code"
      v-model:language="language"
      v-model:self-test-input="selfTestInput"
      :problem="problem"
      :submitting="submitting"
      :submit-disabled="!code.trim()"
      :self-testing="selfTesting"
      :self-test-result="selfTestResult"
      hide-published-status
      @show-submissions="subsVisible = true"
      @submit="submit"
      @self-test="runSelfTest"
    />

    <!-- 提交历史弹窗 -->
    <n-modal
      v-model:show="subsVisible"
      preset="card"
      :title="t('problems.detail.mySubmissions')"
      style="width: min(720px, 92vw)"
    >
      <n-data-table
        v-if="mySubmissions.length"
        size="small"
        :columns="submissionColumns"
        :data="mySubmissions"
        :row-props="
          (row: Submission) => ({ style: 'cursor: pointer;', onClick: () => openSubmission(row) })
        "
      />
      <n-empty v-else :description="t('problems.detail.noSubmissions')" />
    </n-modal>
  </div>
</template>
