<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import BaseAvatar from '@/components/common/BaseAvatar.vue'
import EntityCard from '@/components/common/EntityCard.vue'
import ContestStatusBadge from '@/components/contests/ContestStatusBadge.vue'
import { formatDateTime } from '@/utils/format'
import type { ContestSummary } from '@/types'

defineProps<{ contest: ContestSummary }>()

const emit = defineEmits<{ open: [contest: ContestSummary] }>()

const { t } = useI18n()
</script>

<template>
  <EntityCard @select="emit('open', contest)">
    <div class="flex items-start gap-3">
      <BaseAvatar
        kind="contest"
        :src="contest.logo"
        :name="contest.title"
        :size="42"
        :round="false"
        :radius="10"
        bordered
      />
      <div class="min-w-0 flex-1">
        <div class="flex items-start gap-2">
          <h3 class="line-clamp-2 min-w-0 flex-1 text-sm font-semibold leading-5">
            {{ contest.title }}
          </h3>
          <div class="shrink-0">
            <ContestStatusBadge :status="contest.status" />
          </div>
        </div>
        <p class="mt-1.5 line-clamp-2 min-h-[2.5rem] text-[13px] leading-5 text-muted-foreground">
          {{ contest.description || t('contests.detail.noDescription') }}
        </p>
      </div>
    </div>

    <div class="mt-auto space-y-1 pt-3 text-xs text-muted-foreground">
      <div class="tabular-nums">
        {{ formatDateTime(contest.start_time) }} – {{ formatDateTime(contest.end_time) }}
      </div>
      <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span>{{ contest.rule_type }}</span>
        <span>{{ t('contests.list.problemCount', { count: contest.problem_count }) }}</span>
        <span>{{ t('contests.list.registeredCount', { count: contest.registered_count }) }}</span>
        <span v-if="contest.board_frozen">{{ t('contests.boardFrozenTag') }}</span>
      </div>
    </div>
  </EntityCard>
</template>
