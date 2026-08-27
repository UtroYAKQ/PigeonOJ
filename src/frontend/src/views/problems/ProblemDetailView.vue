<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { DataTableColumns } from 'naive-ui'

import { createSubmission, listSubmissions } from '@/api/judge'
import { getProblem } from '@/api/problems'
import { useCodeDraft } from '@/composables/useCodeDraft'
import { useSelfTest } from '@/composables/useSelfTest'
import { dialog, message } from '@/utils/feedback'
import StatusTag from '@/components/StatusTag.vue'
import ProblemWorkbench from '@/components/problem/ProblemWorkbench.vue'
import type {
  ProblemDetailEx,
  ProblemLanguage,
  Submission,
} from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const problem = ref<ProblemDetailEx | null>(null)
const submitting = ref(false)
const subsVisible = ref(false)
const language = ref<ProblemLanguage>('cpp17')
const mySubmissions = ref<Submission[]>([])

const code = ref('')

// 代码本地草稿：进入恢复、编辑防抖保存、切换语言分语言存档（提交/切页返回不丢）
const { restore: restoreDraft } = useCodeDraft({
  problemId: () => String(route.params.id),
  code,
  language,
})

// 用户自测：控制台状态在 composable 内（docs/contracts/judge.md「用户自测」）
const { selfTestInput, selfTesting, selfTestResult, runSelfTest: doSelfTest } = useSelfTest(
  () => String(route.params.id),
)

async function load() {
  try {
    problem.value = await getProblem(String(route.params.id))
    await loadMySubmissions()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
  }
}
async function loadMySubmissions() {
  try {
    const result = await listSubmissions({ problem_id: String(route.params.id), page_size: 5 })
    mySubmissions.value = result.items
  } catch {
    /* 未登录等场景静默 */
  }
}

function openSubmission(row: Submission) {
  subsVisible.value = false
  router.push(`/problems/${route.params.id}/submissions/${row.id}`)
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
      submitting.value = true
      try {
        const result = await createSubmission({
          problem_id: problem.value!.id,
          language: language.value,
          code: code.value,
        })
        router.push(`/problems/${problem.value!.id}/submissions/${result.submission_id}`)
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
        :row-props="(row: Submission) => ({ style: 'cursor: pointer;', onClick: () => openSubmission(row) })"
      />
      <n-empty v-else :description="t('problems.detail.noSubmissions')" />
    </n-modal>
  </div>
</template>
