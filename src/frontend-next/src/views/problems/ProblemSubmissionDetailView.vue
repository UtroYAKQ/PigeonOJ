<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'

import { getProblemSubmission } from '@/api/problems'
import SubmissionResultPage from '@/components/submission/SubmissionResultPage.vue'
import { useSubmissionPolling } from '@/composables/useSubmissionPolling'

const route = useRoute()

const problemId = String(route.params.problemId ?? route.params.id)

const { submission, loading, pollingStopped, load, refreshNow } = useSubmissionPolling(() =>
  getProblemSubmission(problemId, String(route.params.sid)),
)

onMounted(() => {
  void load()
})
</script>

<template>
  <SubmissionResultPage
    :submission="submission"
    :loading="loading"
    :polling-stopped="pollingStopped"
    :refreshing="loading"
    @refresh="refreshNow"
  />
</template>