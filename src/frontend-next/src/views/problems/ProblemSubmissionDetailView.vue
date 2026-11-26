<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { getProblemSubmission } from '@/api/problems'
import SubmissionResultPage from '@/components/submission/SubmissionResultPage.vue'
import { useSubmissionPolling } from '@/composables/useSubmissionPolling'
import { goBackOrFallback } from '@/utils/navigation'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const problemId = String(route.params.problemId ?? route.params.id)
const backLabel = computed(() =>
  route.meta.backLabelKey
    ? t(String(route.meta.backLabelKey))
    : t('problems.submissionsManage.backToList'),
)

const { submission, loading, pollingStopped, load, refreshNow } = useSubmissionPolling(() =>
  getProblemSubmission(problemId, String(route.params.sid)),
)

function back(): void {
  goBackOrFallback(
    router,
    String(route.meta.backFallback ?? `/admin/problems/${problemId}/submissions`),
  )
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