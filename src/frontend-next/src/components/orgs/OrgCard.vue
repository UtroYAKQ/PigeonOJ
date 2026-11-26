<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Boxes, CalendarDays, ChevronRight, Users } from '@lucide/vue'

import BaseAvatar from '@/components/common/BaseAvatar.vue'
import EntityCard from '@/components/common/EntityCard.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import { formatDateTime } from '@/utils/format'
import type { OrgSummary } from '@/types'

defineProps<{ org: OrgSummary }>()

const emit = defineEmits<{ open: [org: OrgSummary] }>()

const { t } = useI18n()
</script>

<template>
  <EntityCard @select="emit('open', org)">
    <div class="flex items-start gap-3">
      <BaseAvatar
        kind="team"
        :src="org.avatar_url"
        :name="org.name"
        :size="42"
        :round="false"
        :radius="10"
        bordered
      />
      <div class="min-w-0 flex-1">
        <div class="flex min-w-0 items-center gap-2">
          <h3 class="truncate text-[14px] font-semibold">{{ org.name }}</h3>
          <ToneBadge
            v-if="org.my_role"
            :tone="org.my_role === 'admin' ? 'warning' : 'default'"
            dot
            :label="org.my_role === 'admin' ? t('orgs.role.admin') : t('orgs.role.member')"
          />
        </div>
        <p class="mt-1.5 line-clamp-2 min-h-[2.5rem] text-[12.5px] leading-5 text-muted-foreground">
          {{ org.description || t('orgs.detail.descEmpty') }}
        </p>
      </div>
    </div>

    <div
      class="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1.5 pt-3 text-[12px] text-muted-foreground"
    >
      <span class="inline-flex items-center gap-1.5">
        <Users class="size-3.5" aria-hidden="true" />
        {{ t('orgs.list.memberCountValue', { count: org.member_count }) }}
      </span>
      <span class="inline-flex items-center gap-1.5">
        <Boxes class="size-3.5" aria-hidden="true" />
        {{ t('orgs.list.teamCountValue', { count: org.team_count }) }}
      </span>
      <span class="inline-flex items-center gap-1.5">
        <CalendarDays class="size-3.5" aria-hidden="true" />
        {{ formatDateTime(org.created_at) }}
      </span>
      <ChevronRight
        class="ml-auto size-4 shrink-0 text-muted-foreground/60 transition-transform group-hover:translate-x-0.5"
        aria-hidden="true"
      />
    </div>
  </EntityCard>
</template>
