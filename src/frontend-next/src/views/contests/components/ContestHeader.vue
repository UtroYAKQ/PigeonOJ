<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Ellipsis, Loader2 } from '@lucide/vue'

import BaseAvatar from '@/components/common/BaseAvatar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import ContestCountdown from '@/components/contests/ContestCountdown.vue'
import ContestStatusBadge from '@/components/contests/ContestStatusBadge.vue'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { formatDateTime } from '@/utils/format'
import type { ContestDetail } from '@/types'

defineProps<{
  detail: ContestDetail
  now: number
  registering?: boolean
}>()

const emit = defineEmits<{
  register: []
  edit: []
  tools: []
}>()

const { t } = useI18n()
</script>

<template>
  <Card class="shrink-0 px-4 py-4 md:px-5">
    <div class="flex flex-wrap items-start gap-4">
      <BaseAvatar
        kind="contest"
        :src="detail.logo"
        :name="detail.title"
        :size="64"
        :round="false"
        :radius="10"
        bordered
      />

      <div class="min-w-0 flex-1 space-y-2">
        <div class="flex flex-wrap items-center gap-2">
          <h1 class="min-w-0 truncate text-[20px] font-semibold leading-tight tracking-tight">
            {{ detail.title }}
          </h1>
          <ContestStatusBadge :status="detail.status" />
          <ToneBadge tone="default" :label="detail.rule_type" />
          <ToneBadge
            v-if="detail.my_registration === 'registered'"
            tone="success"
            :label="t('contests.detail.registered')"
          />
          <ToneBadge
            v-if="detail.board_frozen"
            tone="warning"
            :label="t('contests.boardFrozenTag')"
          />
        </div>

        <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-muted-foreground">
          <span>
            {{ t('contests.detail.problems') }}
            <strong class="font-semibold text-foreground">{{ detail.problem_count }}</strong>
          </span>
          <span aria-hidden="true">·</span>
          <span>
            {{ t('contests.detail.registeredCount') }}
            <strong class="font-semibold text-foreground">{{ detail.registered_count }}</strong>
          </span>
          <span aria-hidden="true">·</span>
          <span class="tabular-nums">
            {{ formatDateTime(detail.start_time) }} → {{ formatDateTime(detail.end_time) }}
          </span>
        </div>
      </div>

      <div class="flex shrink-0 flex-wrap items-center gap-2">
        <ContestCountdown
          :start-time="detail.start_time"
          :end-time="detail.end_time"
          :status="detail.status"
          :now="now"
        />
        <Button
          v-if="detail.can_register"
          size="sm"
          :disabled="registering"
          @click="emit('register')"
        >
          <Loader2 v-if="registering" class="size-4 animate-spin" />
          {{ t('contests.detail.register') }}
        </Button>
        <DropdownMenu v-if="detail.can_manage">
          <DropdownMenuTrigger as-child>
            <Button variant="ghost" size="icon-sm" :aria-label="t('teams.detail.more')">
              <Ellipsis class="size-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" class="w-44">
            <DropdownMenuItem :disabled="detail.status !== 'scheduled'" @select="emit('edit')">
              {{ t('contests.detail.manage') }}
            </DropdownMenuItem>
            <DropdownMenuItem @select="emit('tools')">
              {{ t('contests.tools.title') }}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  </Card>
</template>
