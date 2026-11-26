<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { getSubmission } from '@/api/judge'
import SubmissionResultPage from '@/components/submission/SubmissionResultPage.vue'
import { useSubmissionPolling } from '@/composables/useSubmissionPolling'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const { submission, loading, pollingStopped, load, refreshNow } = useSubmissionPolling(() =>
  getSubmission(String(route.params.id)),
)

const canGoBack = computed(() => {
  const back = router.options.history.state.back
  return typeof back === 'string' && back.length > 0 && back !== route.fullPath
})

const backLabel = computed(() => {
  if (canGoBack.value) return t('problems.submission.back')
  return submission.value?.problem_id
    ? t('problems.submission.backToProblem')
    : t('problems.submission.back')
})

function back(): void {
  if (canGoBack.value) {
    router.back()
    return
  }
  if (route.params.teamId && route.params.cid && route.params.problemId) {
    router.push(
      `/teams/${String(route.params.teamId)}/contests/${String(route.params.cid)}/problems/${String(route.params.problemId)}`,
    )
  } else if (route.params.setId && route.params.problemId) {
    router.push(
      `/problem-sets/${String(route.params.setId)}/problems/${String(route.params.problemId)}`,
    )
  } else if (route.params.cid && route.params.problemId) {
    router.push(`/contests/${String(route.params.cid)}/problems/${String(route.params.problemId)}`)
  } else if (route.params.teamId && route.params.problemId) {
    router.push(`/teams/${String(route.params.teamId)}/problems/${String(route.params.problemId)}`)
  } else if (submission.value?.problem_id) {
    router.push(`/problems/${submission.value.problem_id}`)
  } else {
    router.push('/problems/list')
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <SubmissionResultPage
    :submission="submission"
    :loading="loading"
    :polling-stopped="pollingStopped"
    :back-label="backLabel"
    :refreshing="loading"
    @refresh="refreshNow"
    @back="back"
  />
</template>