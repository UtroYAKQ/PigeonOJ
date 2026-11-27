<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import EmptyState from '@/components/common/EmptyState.vue'
import PageShell from '@/components/common/PageShell.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SubmissionResult from '@/components/submission/SubmissionResult.vue'
import type { Submission } from '@/types'

withDefaults(
  defineProps<{
    submission: Submission | null
    loading: boolean
    pollingStopped?: boolean
    refreshing?: boolean
  }>(),
  { pollingStopped: false, refreshing: false },
)

const emit = defineEmits<{ refresh: [] }>()
const { t } = useI18n()
</script>

<template>
  <PageShell
    :title="t('problems.submission.title')"
    :description="t('problems.submission.description')"
    :fill="!submission"
  >
    <div v-if="loading && !submission" class="grid min-h-[320px] flex-1 place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <SubmissionResult
      v-else-if="submission"
      :submission="submission"
      :polling-stopped="pollingStopped"
    >
      <template #status-actions>
        <RefreshButton
          :loading="refreshing"
          :label="t('action.refresh')"
          @click="emit('refresh')"
        />
      </template>
    </SubmissionResult>

    <div v-else class="grid min-h-[320px] flex-1 place-items-center">
      <EmptyState :text="t('common.noData')" />
    </div>
  </PageShell>
</template>
