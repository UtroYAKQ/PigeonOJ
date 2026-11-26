<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import BaseAvatar from '@/components/common/BaseAvatar.vue'
import EntityCard from '@/components/common/EntityCard.vue'
import TeamRoleBadge from '@/components/teams/TeamRoleBadge.vue'
import { formatDate } from '@/utils/format'
import type { TeamSummary } from '@/types'

defineProps<{
  team: TeamSummary
  mineOnly: boolean
  applied: boolean
}>()

const emit = defineEmits<{ open: [team: TeamSummary] }>()

const { t } = useI18n()
</script>

<template>
  <EntityCard @select="emit('open', team)">
    <div class="flex items-start gap-3">
      <BaseAvatar
        kind="team"
        :src="team.avatar_url"
        :name="team.name"
        :size="36"
        :round="false"
        :radius="8"
        bordered
      />
      <div class="min-w-0 flex-1">
        <div class="flex min-w-0 items-center gap-2">
          <h3 :title="team.name" class="min-w-0 flex-1 truncate text-[14px] font-semibold leading-5">
            {{ team.name }}
          </h3>
          <TeamRoleBadge v-if="team.my_role" :role="team.my_role" class="shrink-0" />
        </div>
        <p class="mt-1 line-clamp-1 min-h-5 text-[12.5px] leading-5 text-muted-foreground">
          {{ team.description || t('teams.detail.descEmpty') }}
        </p>
      </div>
    </div>

    <div class="mt-3 flex items-center gap-2 text-[12px] tabular-nums text-muted-foreground">
      {{ t('teams.list.memberCountValue', { count: team.member_count }) }}
    </div>

    <div
      class="mt-auto flex items-center border-t border-border pt-2.5 text-[11px] tabular-nums text-muted-foreground"
    >
      <span class="truncate">
        {{ t('common.createdAtValue', { time: formatDate(team.created_at) }) }}
      </span>
    </div>
  </EntityCard>
</template>