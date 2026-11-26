<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import { createSubmission } from '@/api/judge'
import { getOrgProblem } from '@/api/orgs'
import { getProblem } from '@/api/problems'
import { createProblemSetSubmission, getProblemSetProblem } from '@/api/problemSets'
import { createContestSubmission, getContestProblem } from '@/api/contests'
import {
  createTeamContestSubmission,
  createTeamProblemSubmission,
  createTeamSetProblemSubmission,
  getTeamContestProblem,
  getTeamProblem,
  getTeamSetProblem,
  runTeamProblemCode,
  runTeamSetProblemCode,
} from '@/api/teams'
import MySubmissionsDialog from '@/components/problem/MySubmissionsDialog.vue'
import ProblemWorkbench from '@/components/problem/ProblemWorkbench.vue'
import { useCodeDraft } from '@/composables/useCodeDraft'
import { useSelfTest } from '@/composables/useSelfTest'
import { confirmDialog, message } from '@/utils/feedback'
import type { ProblemDetail, ProblemLanguage } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const problem = ref<ProblemDetail | null>(null)
const problemLoading = ref(true)
const submitting = ref(false)
const subsVisible = ref(false)
const language = ref<ProblemLanguage>('cpp17')

const problemId = computed(() => String(route.params.problemId ?? route.params.id))
const orgId = computed(() => (route.params.orgId ? String(route.params.orgId) : null))
const context = computed<
  'problems' | 'problem-sets' | 'contests' | 'teams' | 'team-sets' | 'team-contests' | 'orgs'
>(() =>
  orgId.value
    ? 'orgs'
    : route.params.teamId && route.params.cid
    ? 'team-contests'
    : route.params.cid
      ? 'contests'
      : route.params.setId && route.params.teamId
        ? 'team-sets'
        : route.params.setId
          ? 'problem-sets'
          : route.params.teamId
            ? 'teams'
            : 'problems',
)
const contextId = computed(() =>
  context.value === 'contests' || context.value === 'team-contests'
    ? String(route.params.cid)
    : context.value === 'team-sets' || context.value === 'problem-sets'
      ? String(route.params.setId)
      : context.value === 'teams'
        ? String(route.params.teamId)
        : '',
)
const teamContextId = computed(() =>
  context.value === 'team-sets' || context.value === 'teams' ? String(route.params.teamId) : '',
)
const submissionsBase = computed(() => {
  if (context.value === 'orgs') {
    return `/orgs/${orgId.value}/problems/${problemId.value}`
  }
  if (context.value === 'contests') {
    return `/contests/${contextId.value}/problems/${problemId.value}`
  }
  if (context.value === 'team-contests') {
    return `/teams/${String(route.params.teamId)}/contests/${contextId.value}/problems/${problemId.value}`
  }
  if (context.value === 'team-sets') {
    return `/teams/${teamContextId.value}/sets/${contextId.value}/problems/${problemId.value}`
  }
  if (context.value === 'problem-sets') {
    return `/problem-sets/${contextId.value}/problems/${problemId.value}`
  }
  if (context.value === 'teams') {
    return `/teams/${contextId.value}/problems/${problemId.value}`
  }
  return `/problems/${problemId.value}`
})

const solutionsHref = computed(() =>
  context.value === 'teams' || context.value === 'team-sets' || context.value === 'team-contests'
    ? undefined
    : `${submissionsBase.value}/solutions`,
)

const code = ref('')
const { restore: restoreDraft } = useCodeDraft({
  problemId: () => problemId.value,
  code,
  language,
})

const {
  selfTestInput,
  selfTesting,
  selfTestResult,
  runSelfTest: doSelfTest,
} = useSelfTest(() => problemId.value, {
  runner:
    context.value === 'team-sets'
      ? (payload) =>
          runTeamSetProblemCode(teamContextId.value, contextId.value, payload.problem_id, {
            language: payload.language,
            code: payload.code,
            input: payload.input,
          })
      : context.value === 'teams'
        ? (payload) =>
            runTeamProblemCode(String(route.params.teamId), payload.problem_id, {
              language: payload.language,
              code: payload.code,
              input: payload.input,
            })
        : undefined,
})

async function load(): Promise<void> {
  problemLoading.value = true
  try {
    problem.value =
      context.value === 'orgs'
        ? await getOrgProblem(orgId.value!, problemId.value)
        : context.value === 'team-contests'
        ? await getTeamContestProblem(String(route.params.teamId), contextId.value, problemId.value)
        : context.value === 'contests'
          ? await getContestProblem(contextId.value, problemId.value)
          : context.value === 'team-sets'
            ? await getTeamSetProblem(teamContextId.value, contextId.value, problemId.value)
            : context.value === 'problem-sets'
              ? await getProblemSetProblem(contextId.value, problemId.value)
              : context.value === 'teams'
                ? await getTeamProblem(contextId.value, problemId.value)
                : await getProblem(problemId.value)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
  } finally {
    problemLoading.value = false
  }
}

function openSubs(): void {
  subsVisible.value = true
}

async function submit(): Promise<void> {
  if (!problem.value || submitting.value) return
  if (!code.value.trim()) {
    message.warning(t('problems.detail.codeRequired'))
    return
  }
  const ok = await confirmDialog({
    title: t('problems.detail.submit'),
    content: t('problems.detail.submitConfirm'),
    positiveText: t('problems.detail.submit'),
    negativeText: t('action.cancel'),
  })
  if (!ok) return

  const current = problem.value
  if (!current) return
  submitting.value = true
  try {
    let result: { submission_id: string }
    if (context.value === 'team-contests') {
      result = await createTeamContestSubmission(
        String(route.params.teamId),
        contextId.value,
        current.id,
        { language: language.value, code: code.value },
      )
    } else if (context.value === 'contests') {
      result = await createContestSubmission(contextId.value, current.id, {
        language: language.value,
        code: code.value,
      })
    } else if (context.value === 'team-sets') {
      result = await createTeamSetProblemSubmission(
        teamContextId.value,
        contextId.value,
        current.id,
        { language: language.value, code: code.value },
      )
    } else if (context.value === 'problem-sets') {
      result = await createProblemSetSubmission(contextId.value, current.id, {
        language: language.value,
        code: code.value,
      })
    } else if (context.value === 'teams') {
      result = await createTeamProblemSubmission(contextId.value, current.id, {
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
}

async function runSelfTest(): Promise<void> {
  if (!problem.value) return
  await doSelfTest({ language: language.value, code: code.value })
}

onMounted(() => {
  restoreDraft()
  void load()
})
</script>

<template>
  <div class="min-h-[60vh] p-3 min-[900px]:h-[calc(100dvh-3.5rem)]">
    <div v-if="problemLoading" class="grid h-full place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <ProblemWorkbench
      v-else-if="problem"
      v-model:code="code"
      v-model:language="language"
      v-model:self-test-input="selfTestInput"
      :problem="problem"
      :submitting="submitting"
      :submit-disabled="!code.trim()"
      :self-testing="selfTesting"
      :self-test-result="selfTestResult"
      :solutions-href="solutionsHref"
      :show-solution="false"
      hide-published-status
      @show-submissions="openSubs"
      @submit="submit"
      @self-test="runSelfTest"
    />

    <div v-else class="grid h-full place-items-center text-[13px] text-muted-foreground">
      {{ t('problems.detail.loadFailed') }}
    </div>

    <MySubmissionsDialog
      v-model:open="subsVisible"
      :problem-id="problemId"
      :submissions-base="submissionsBase"
    />
  </div>
</template>
