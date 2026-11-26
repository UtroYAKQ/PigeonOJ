<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import BaseAvatar from '@/components/common/BaseAvatar.vue'
import { Badge } from '@/components/ui/badge'
import type { TeamMemberItem } from '@/types'

defineProps<{
  member: TeamMemberItem
  isSelf: boolean
}>()

const { t } = useI18n()
</script>

<template>
  <div class="flex min-w-0 items-center gap-2.5 py-0.5">
    <BaseAvatar :src="member.avatar_url" :name="member.nickname" :size="30" />
    <div class="min-w-0">
      <div class="flex min-w-0 items-center gap-1.5">
        <span class="truncate text-[13px] font-medium" :title="member.nickname">
          {{ member.nickname }}
        </span>
        <Badge
          v-if="isSelf"
          variant="secondary"
          class="h-4 shrink-0 px-1.5 text-[10px] font-medium"
        >
          {{ t('teams.members.you') }}
        </Badge>
      </div>
      <p
        v-if="member.note"
        class="max-w-[260px] truncate text-[11.5px] text-muted-foreground"
        :title="member.note"
      >
        {{ member.note }}
      </p>
    </div>
  </div>
</template>
