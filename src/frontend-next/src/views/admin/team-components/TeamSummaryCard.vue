<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import BaseAvatar from '@/components/common/BaseAvatar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import { formatDateTime } from '@/utils/format'
import type { TeamAdminDetail } from '@/types'

const props = defineProps<{ detail: TeamAdminDetail }>()

const { t } = useI18n()

const isActive = computed(() => props.detail.status === 'active')
</script>

<template>
  <section
    class="flex shrink-0 flex-col gap-4 rounded-lg border border-border bg-card p-4 sm:flex-row sm:items-start md:p-5"
  >
    <BaseAvatar
      kind="team"
      :src="detail.avatar_url"
      :name="detail.name"
      :size="68"
      :round="false"
      :radius="12"
      bordered
    />

    <div class="min-w-0 flex-1">
      <div class="flex flex-wrap items-center gap-2">
        <h1 class="truncate text-lg font-semibold leading-tight tracking-tight">
          {{ detail.name }}
        </h1>
        <ToneBadge
          tone="warning"
          :label="`${t('admin.teams.creator')} · ${detail.creator_nickname ?? '—'}`"
        />
        <ToneBadge
          :tone="isActive ? 'success' : 'danger'"
          :label="t(isActive ? 'admin.teams.statusActive' : 'admin.teams.statusDisbanded')"
        />
      </div>

      <p
        class="mt-1.5 line-clamp-2 text-[13px] leading-5 text-muted-foreground"
        :class="{ 'opacity-70': !detail.description }"
      >
        {{ detail.description ?? t('admin.teams.descEmpty') }}
      </p>

      <div
        class="mt-2 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[12px] text-muted-foreground"
      >
        <span>
          {{ t('admin.teams.memberCount') }}
          <strong class="font-semibold text-foreground">{{ detail.member_count }}</strong>
        </span>
        <span aria-hidden="true">·</span>
        <span>{{ t('admin.teams.createdAt') }} {{ formatDateTime(detail.created_at) }}</span>
        <template v-if="!isActive">
          <span aria-hidden="true">·</span>
          <span class="text-destructive">
            {{ t('admin.teams.disbandedAt') }} {{ formatDateTime(detail.disbanded_at) }}
          </span>
        </template>
        <span aria-hidden="true">·</span>
        <span class="font-mono" :title="detail.id">
          {{ t('admin.teams.teamId') }} {{ detail.id.slice(0, 8) }}
        </span>
      </div>
    </div>

    <div
      class="flex shrink-0 items-center justify-around gap-6 border-t border-border pt-3 sm:justify-start sm:border-l sm:border-t-0 sm:pl-6 sm:pt-0"
    >
      <div class="flex min-w-[52px] flex-col items-center gap-0.5">
        <span class="text-lg font-semibold leading-tight tabular-nums">{{
          detail.problem_count
        }}</span>
        <span class="whitespace-nowrap text-[11.5px] text-muted-foreground">
          {{ t('admin.teams.statProblems') }}
        </span>
      </div>
      <div class="flex min-w-[52px] flex-col items-center gap-0.5">
        <span class="text-lg font-semibold leading-tight tabular-nums">
          {{ detail.problem_set_count }}
        </span>
        <span class="whitespace-nowrap text-[11.5px] text-muted-foreground">
          {{ t('admin.teams.statSets') }}
        </span>
      </div>
      <div class="flex min-w-[52px] flex-col items-center gap-0.5">
        <span class="text-lg font-semibold leading-tight tabular-nums">{{
          detail.contest_count
        }}</span>
        <span class="whitespace-nowrap text-[11.5px] text-muted-foreground">
          {{ t('admin.teams.statContests') }}
        </span>
      </div>
    </div>
  </section>
</template>
