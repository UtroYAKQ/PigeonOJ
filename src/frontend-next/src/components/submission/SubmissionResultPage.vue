<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ArrowLeft, Loader2 } from '@lucide/vue'

import EmptyState from '@/components/common/EmptyState.vue'
import PageShell from '@/components/common/PageShell.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SubmissionResult from '@/components/submission/SubmissionResult.vue'
import { Button } from '@/components/ui/button'
import type { Submission } from '@/types'

withDefaults(
  defineProps<{
    submission: Submission | null
    loading: boolean
    pollingStopped?: boolean
    backLabel?: string
    refreshing?: boolean
  }>(),
  { pollingStopped: false, backLabel: undefined, refreshing: false },
)

const emit = defineEmits<{ refresh: []; back: [] }>()
const { t } = useI18n()
</script>

<template>
  <PageShell
    :title="t('problems.submission.title')"
    :description="t('problems.submission.description')"
  >
    <template #actions>
      <RefreshButton
        v-if="submission"
        :loading="refreshing"
        :label="t('action.refresh')"
        @click="emit('refresh')"
      />
      <Button variant="outline" size="sm" @click="emit('back')">
        <ArrowLeft class="size-4" />
        {{ backLabel ?? t('problems.submission.back') }}
      </Button>
    </template>

    <div v-if="loading && !submission" class="grid min-h-[320px] place-items-center">
      <Loader2 class="size-6 animate-spin text-muted-foreground" />
    </div>

    <SubmissionResult
      v-else-if="submission"
      :submission="submission"
      :polling-stopped="pollingStopped"
    />

    <div v-else class="grid min-h-[320px] place-items-center">
      <EmptyState :text="t('common.noData')" />
    </div>
  </PageShell>
</template>
