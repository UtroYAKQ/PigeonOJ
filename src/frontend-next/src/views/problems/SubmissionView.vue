<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'

import { getSubmission } from '@/api/judge'
import SubmissionResultPage from '@/components/submission/SubmissionResultPage.vue'
import { useSubmissionPolling } from '@/composables/useSubmissionPolling'

const route = useRoute()

const { submission, loading, pollingStopped, load, refreshNow } = useSubmissionPolling(() =>
  getSubmission(String(route.params.id)),
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