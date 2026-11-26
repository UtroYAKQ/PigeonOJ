<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import MarkdownView from '@/components/common/MarkdownView.vue'
import ProblemSamples from '@/components/problem/ProblemSamples.vue'
import type { ProblemDetail } from '@/types'

withDefaults(
  defineProps<{
    problem: Pick<
      ProblemDetail,
      | 'background'
      | 'description'
      | 'input_description'
      | 'output_description'
      | 'samples'
      | 'note'
      | 'solution'
    >
    showSolution?: boolean
  }>(),
  { showSolution: true },
)

const { t } = useI18n()
</script>

<template>
  <div>
    <template v-if="problem.background">
      <h3 class="mt-0 border-0 pt-0 text-[15px] font-semibold">
        {{ t('problems.detail.background') }}
      </h3>
      <MarkdownView :source="problem.background" />
    </template>

    <h3
      class="mb-2 mt-6 border-t border-border pt-4 text-[15px] font-semibold"
      :class="{ 'mt-0 border-0 pt-0': !problem.background }"
    >
      {{ t('problems.detail.description') }}
    </h3>
    <MarkdownView :source="problem.description" />

    <h3 class="mb-2 mt-6 border-t border-border pt-4 text-[15px] font-semibold">
      {{ t('problems.detail.inputDescription') }}
    </h3>
    <MarkdownView :source="problem.input_description || ''" />

    <h3 class="mb-2 mt-6 border-t border-border pt-4 text-[15px] font-semibold">
      {{ t('problems.detail.outputDescription') }}
    </h3>
    <MarkdownView :source="problem.output_description || ''" />

    <template v-if="problem.samples?.length">
      <h3 class="mb-2 mt-6 border-t border-border pt-4 text-[15px] font-semibold">
        {{ t('problems.detail.samples') }}
      </h3>
      <ProblemSamples :samples="problem.samples" />
    </template>

    <template v-if="problem.note">
      <h3 class="mb-2 mt-6 border-t border-border pt-4 text-[15px] font-semibold">
        {{ t('problems.detail.note') }}
      </h3>
      <MarkdownView :source="problem.note" />
    </template>

    <template v-if="showSolution && problem.solution">
      <h3 class="mb-2 mt-6 border-t border-border pt-4 text-[15px] font-semibold">
        {{ t('problems.detail.solution') }}
      </h3>
      <MarkdownView :source="problem.solution" />
    </template>
  </div>
</template>
