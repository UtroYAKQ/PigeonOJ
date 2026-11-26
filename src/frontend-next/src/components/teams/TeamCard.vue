<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { CalendarDays, ChevronRight, Users } from '@lucide/vue'

import BaseAvatar from '@/components/common/BaseAvatar.vue'
import EntityCard from '@/components/common/EntityCard.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import TeamRoleBadge from '@/components/teams/TeamRoleBadge.vue'
import { formatDateTime } from '@/utils/format'
import type { TeamSummary } from '@/types'

const props = defineProps<{
  team: TeamSummary
  mineOnly: boolean
  applied: boolean
}>()

const emit = defineEmits<{ open: [team: TeamSummary] }>()

const { t } = useI18n()

const actionLabel = computed(() => {
  if (props.team.my_role) return t('action.view')
  if (props.mineOnly) return ''
  if (props.applied) return t('teams.list.appliedTag')
  return t('teams.list.applyJoin')
})

/** 待审核状态不再暗示可跳转 */
const showArrow = computed(() => Boolean(props.team.my_role) || !props.applied)
</script>

<template>
  <EntityCard @select="emit('open', team)">
    <div class="flex items-start gap-3">
      <BaseAvatar
        kind="team"
        :src="team.avatar_url"
        :name="team.name"
        :size="42"
        :round="false"
        :radius="10"
        bordered
      />
      <div class="min-w-0 flex-1">
        <div class="flex min-w-0 items-center gap-2">
          <h3 class="truncate text-[14px] font-semibold">{{ team.name }}</h3>
          <TeamRoleBadge v-if="team.my_role" :role="team.my_role" />
          <ToneBadge v-else-if="!mineOnly" tone="info" :label="t('teams.list.publicTeam')" />
        </div>
        <p class="mt-1.5 line-clamp-2 min-h-[2.5rem] text-[12.5px] leading-5 text-muted-foreground">
          {{ team.description || t('teams.detail.descEmpty') }}
        </p>
      </div>
    </div>

    <div
      class="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1.5 pt-3 text-[12px] text-muted-foreground"
    >
      <span class="inline-flex items-center gap-1.5">
        <Users class="size-3.5" aria-hidden="true" />
        {{ t('teams.list.memberCountValue', { count: team.member_count }) }}
      </span>
      <span class="inline-flex items-center gap-1.5">
        <CalendarDays class="size-3.5" aria-hidden="true" />
        {{ formatDateTime(team.created_at) }}
      </span>
      <span
        v-if="actionLabel"
        class="ml-auto inline-flex items-center gap-1 text-[12px] font-medium text-foreground/70 transition-colors group-hover:text-brand"
      >
        {{ actionLabel }}
        <ChevronRight
          v-if="showArrow"
          class="size-3.5 transition-transform group-hover:translate-x-0.5"
          aria-hidden="true"
        />
      </span>
    </div>
  </EntityCard>
</template>
