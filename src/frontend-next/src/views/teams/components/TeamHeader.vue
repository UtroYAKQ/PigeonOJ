<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Copy, Link2, Settings2 } from '@lucide/vue'

import BaseAvatar from '@/components/common/BaseAvatar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import TeamRoleBadge from '@/components/teams/TeamRoleBadge.vue'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { copyToClipboard } from '@/utils/clipboard'
import { message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { TeamDetail } from '@/types'

const props = defineProps<{
  team: TeamDetail
  isAdmin: boolean
  isCreator: boolean
}>()

const emit = defineEmits<{
  invite: []
  edit: []
}>()

const { t } = useI18n()

async function copyTeamId(): Promise<void> {
  const ok = await copyToClipboard(props.team.id)
  if (ok) message.success(t('common.copied'))
  else message.error(t('common.copyFailed'))
}
</script>

<template>
  <Card class="shrink-0 px-4 py-4 md:px-5">
    <div class="flex flex-wrap items-start gap-4">
      <BaseAvatar
        kind="team"
        :src="team.avatar_url"
        :name="team.name"
        :size="64"
        :round="false"
        :radius="12"
        bordered
      />

      <div class="min-w-[200px] flex-1 space-y-2">
        <div class="flex flex-wrap items-center gap-2">
          <h1 class="min-w-0 truncate text-[20px] font-semibold leading-tight tracking-tight">
            {{ team.name }}
          </h1>
          <TeamRoleBadge v-if="team.my_role" :role="team.my_role" />
          <ToneBadge
            tone="default"
            :label="
              team.visibility === 'public'
                ? t('teams.settings.visibilityPublic')
                : t('teams.settings.visibilityPrivate')
            "
          />
        </div>

        <p
          class="max-w-[80ch] text-[13px] leading-5 text-muted-foreground"
          :class="{ 'opacity-60': !team.description }"
        >
          {{ team.description || t('teams.detail.descEmpty') }}
        </p>

        <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-muted-foreground">
          <span>
            {{ t('teams.list.memberCount') }}
            <strong class="font-semibold tabular-nums text-foreground">{{
              team.member_count
            }}</strong>
          </span>
          <span aria-hidden="true">·</span>
          <span class="tabular-nums">
            {{ t('teams.list.createdAt') }} {{ formatDateTime(team.created_at) }}
          </span>
          <span aria-hidden="true">·</span>
          <button
            type="button"
            class="inline-flex items-center gap-1 tabular-nums transition-colors hover:text-foreground"
            :title="t('teams.detail.teamId')"
            @click="copyTeamId"
          >
            <Copy class="size-3" aria-hidden="true" />
            {{ t('teams.detail.teamId') }} {{ team.id.slice(0, 8) }}
          </button>
        </div>
      </div>

      <div
        v-if="isAdmin || isCreator"
        class="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:shrink-0"
      >
        <Button v-if="isAdmin" size="sm" @click="emit('invite')">
          <Link2 class="size-4" />
          {{ t('teams.detail.inviteMembers') }}
        </Button>
        <Button v-if="isAdmin" variant="outline" size="sm" @click="emit('edit')">
          <Settings2 class="size-4" />
          {{ t('teams.detail.editInfo') }}
        </Button>
      </div>
    </div>
  </Card>
</template>
