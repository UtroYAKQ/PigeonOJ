<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import ToneBadge from '@/components/common/ToneBadge.vue'
import { problemStatusLabelKey } from '@/constants/problemStatus'
import type { ProblemDetail } from '@/types'

const props = defineProps<{
  problem: Pick<
    ProblemDetail,
    | 'title'
    | 'time_limit_ms'
    | 'memory_limit_mb'
    | 'status'
    | 'visibility'
    | 'needs_reverification'
    | 'tags'
    | 'difficulty'
    | 'submission_count'
    | 'accepted_count'
    | 'has_spj'
  >
  showTitle?: boolean
  hidePublishedStatus?: boolean
  showReverifyTag?: boolean
}>()

const { t } = useI18n()

const statusVisible = computed(
  () => !props.hidePublishedStatus || props.problem.status !== 'published',
)
const statusTone = computed(() =>
  props.problem.status === 'published'
    ? ('success' as const)
    : props.problem.status === 'archived'
      ? ('info' as const)
      : ('warning' as const),
)
const passRate = computed(() => {
  const total = props.problem.submission_count ?? 0
  if (!total) return null
  return `${Math.round(((props.problem.accepted_count ?? 0) / total) * 100)}%`
})
</script>

<template>
  <div class="space-y-2.5">
    <h2 v-if="showTitle" class="text-[19px] font-semibold leading-snug tracking-tight">
      {{ problem.title }}
    </h2>

    <div class="flex flex-wrap items-center gap-x-4 gap-y-2 text-[12px] text-muted-foreground">
      <span class="tabular-nums">{{ problem.time_limit_ms }} ms</span>
      <span class="tabular-nums">{{ problem.memory_limit_mb }} MB</span>
      <span v-if="problem.difficulty !== null && problem.difficulty !== undefined">
        {{ t('problems.list.difficulty') }} {{ problem.difficulty }}
      </span>
      <span v-if="passRate">{{ t('problems.list.passRate') }} {{ passRate }}</span>
      <ToneBadge v-if="problem.has_spj" tone="info" :label="t('problems.detail.spjBadge')" />
      <ToneBadge
        v-if="statusVisible"
        :tone="statusTone"
        :label="t(problemStatusLabelKey[problem.status] ?? problem.status)"
      />
      <ToneBadge
        v-if="problem.visibility && problem.visibility !== 'public'"
        tone="info"
        :label="t(`problems.visibility.${problem.visibility}`)"
      />
      <ToneBadge
        v-if="showReverifyTag && problem.needs_reverification"
        tone="warning"
        :label="t('problems.preview.needsReverification')"
      />
    </div>

    <div v-if="problem.tags?.length" class="flex flex-wrap gap-1.5">
      <span
        v-for="tag in problem.tags"
        :key="tag.id"
        class="inline-flex h-5 items-center rounded-md border border-border px-1.5 text-[11.5px] text-muted-foreground"
        :style="tag.color ? { borderColor: `${tag.color}55`, color: tag.color } : undefined"
      >
        {{ tag.name }}
      </span>
    </div>
  </div>
</template>
