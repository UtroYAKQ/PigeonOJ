<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import BaseAvatar from '@/components/common/BaseAvatar.vue'
import EntityCard from '@/components/common/EntityCard.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import { formatDate } from '@/utils/format'
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
        :size="36"
        :round="false"
        :radius="8"
        bordered
      />
      <div class="min-w-0 flex-1">
        <div class="flex min-w-0 items-center gap-2">
          <h3 :title="org.name" class="min-w-0 flex-1 truncate text-[14px] font-semibold leading-5">
            {{ org.name }}
          </h3>
          <ToneBadge
            v-if="org.my_role"
            :tone="org.my_role === 'admin' ? 'warning' : 'default'"
            dot
            :label="org.my_role === 'admin' ? t('orgs.role.admin') : t('orgs.role.member')"
            class="shrink-0"
          />
        </div>
        <p class="mt-1 line-clamp-1 min-h-5 text-[12.5px] leading-5 text-muted-foreground">
          {{ org.description || t('orgs.detail.descEmpty') }}
        </p>
      </div>
    </div>

    <div
      class="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] tabular-nums text-muted-foreground"
    >
      <span>{{ t('orgs.list.memberCountValue', { count: org.member_count }) }}</span>
      <span aria-hidden="true" class="text-muted-foreground/40">·</span>
      <span>{{ t('orgs.list.teamCountValue', { count: org.team_count }) }}</span>
    </div>

    <div
      class="mt-auto flex items-center border-t border-border pt-2.5 text-[11px] tabular-nums text-muted-foreground"
    >
      <span class="truncate">
        {{ t('common.createdAtValue', { time: formatDate(org.created_at) }) }}
      </span>
    </div>
  </EntityCard>
</template>