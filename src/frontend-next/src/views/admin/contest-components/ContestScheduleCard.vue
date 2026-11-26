<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Loader2 } from '@lucide/vue'

import { Button } from '@/components/ui/button'
import { formatDateTime } from '@/utils/format'
import type { ContestDetail } from '@/types'
import DateTimeField from '@/components/common/DateTimeField.vue'
import ContestToolCard from './ContestToolCard.vue'

const props = defineProps<{
  contest: ContestDetail
  freeze: number | null
  /** 正在延时的分钟数（null = 空闲），用于按钮 loading */
  extendingMinutes: number | null
  freezeSaving: boolean
  canExtend: boolean
  canAdjustFreeze: boolean
}>()

defineEmits<{
  'update:freeze': [value: number | null]
  extend: [minutes: number]
  saveFreeze: []
}>()

const { t } = useI18n()

const extendOptions = [
  { minutes: 15, label: 'contests.tools.extendBy15' },
  { minutes: 30, label: 'contests.tools.extendBy30' },
  { minutes: 60, label: 'contests.tools.extendBy60' },
] as const

function freezeDisabledHint(): string {
  return props.contest.board_frozen
    ? t('contests.tools.freezeDisabledFrozen')
    : t('contests.tools.freezeDisabledFinished')
}
</script>

<template>
  <ContestToolCard :title="t('contests.tools.schedule')" :hint="t('contests.tools.extendHint')">
    <p class="text-[12px] text-muted-foreground">
      {{ t('contests.tools.currentEnd') }} {{ formatDateTime(contest.end_time) }}
    </p>

    <div class="flex flex-wrap gap-1.5">
      <Button
        v-for="option in extendOptions"
        :key="option.minutes"
        variant="outline"
        size="sm"
        :disabled="!canExtend || extendingMinutes !== null"
        @click="$emit('extend', option.minutes)"
      >
        <Loader2 v-if="extendingMinutes === option.minutes" class="size-3.5 animate-spin" />
        {{ t(option.label) }}
      </Button>
    </div>
    <p v-if="!canExtend" class="text-[12px] text-muted-foreground">
      {{ t('contests.tools.extendDisabled') }}
    </p>

    <div class="space-y-1.5 border-t border-border pt-3">
      <p class="text-[12px] leading-5 text-muted-foreground">
        {{ t('contests.tools.freezeHint') }}
      </p>
      <DateTimeField
        :model-value="freeze"
        :disabled="!canAdjustFreeze"
        @update:model-value="$emit('update:freeze', $event)"
      />
      <Button
        variant="outline"
        size="sm"
        :disabled="!canAdjustFreeze || freezeSaving"
        @click="$emit('saveFreeze')"
      >
        <Loader2 v-if="freezeSaving" class="size-3.5 animate-spin" />
        {{ t('contests.tools.freezeSave') }}
      </Button>
      <p v-if="!canAdjustFreeze" class="text-[12px] text-muted-foreground">
        {{ freezeDisabledHint() }}
      </p>
    </div>
  </ContestToolCard>
</template>
