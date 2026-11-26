<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import BaseAvatar from '@/components/common/BaseAvatar.vue'
import EntityCard from '@/components/common/EntityCard.vue'
import ContestStatusBadge from '@/components/contests/ContestStatusBadge.vue'
import { formatDateTimeRange } from '@/utils/format'
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
        :size="36"
        :round="false"
        :radius="8"
        bordered
      />
      <div class="min-w-0 flex-1">
        <div class="flex min-w-0 items-center gap-2">
          <h3
            :title="contest.title"
            class="min-w-0 flex-1 truncate text-[14px] font-semibold leading-5"
          >
            {{ contest.title }}
          </h3>
          <div class="shrink-0">
            <ContestStatusBadge :status="contest.status" />
          </div>
        </div>
        <p class="mt-1 line-clamp-1 min-h-5 text-[12.5px] leading-5 text-muted-foreground">
          {{ contest.description || t('contests.detail.noDescription') }}
        </p>
      </div>
    </div>

    <div
      class="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] tabular-nums text-muted-foreground"
    >
      <span>{{ t('contests.list.problemCount', { count: contest.problem_count }) }}</span>
      <span aria-hidden="true" class="text-muted-foreground/40">·</span>
      <span>{{ t('contests.list.registeredCount', { count: contest.registered_count }) }}</span>
      <template v-if="contest.board_frozen">
        <span aria-hidden="true" class="text-muted-foreground/40">·</span>
        <span>{{ t('contests.boardFrozenTag') }}</span>
      </template>
    </div>

    <div
      class="mt-auto flex items-center border-t border-border pt-2.5 text-[11px] tabular-nums text-muted-foreground"
    >
      <span class="truncate">
        {{ formatDateTimeRange(contest.start_time, contest.end_time) }}
      </span>
    </div>
  </EntityCard>
</template>