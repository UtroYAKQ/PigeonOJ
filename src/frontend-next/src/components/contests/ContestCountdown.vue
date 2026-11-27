<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { TONE_TEXT_CLASSES } from '@/components/common/tone'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import type { ContestStatusType } from '@/types'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{
  startTime: string
  endTime: string
  status: ContestStatusType
  /** 父级每秒推进的当前时间戳 */
  now: number
}>()

const { t } = useI18n()

interface CountdownSegment {
  value: string
  unit: string
}

/** 毫秒 → 天:时:分:秒分段（零填充） */
function toSegments(ms: number): CountdownSegment[] {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const days = Math.floor(totalSeconds / 86400)
  const hours = Math.floor((totalSeconds % 86400) / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  const pad = (value: number) => String(value).padStart(2, '0')
  return [
    { value: pad(days), unit: t('contests.detail.unitDay') },
    { value: pad(hours), unit: t('contests.detail.unitHour') },
    { value: pad(minutes), unit: t('contests.detail.unitMinute') },
    { value: pad(seconds), unit: t('contests.detail.unitSecond') },
  ]
}

/** 未开始 → 距开始；进行中 → 距结束；已结束 → null（恒定文案） */
const countdown = computed<{ label: string; segments: CountdownSegment[] } | null>(() => {
  const start = new Date(props.startTime).getTime()
  const end = new Date(props.endTime).getTime()
  const now = props.now
  if (props.status === 'running') {
    return { label: t('contests.detail.endsIn'), segments: toSegments(end - now) }
  }
  if (props.status === 'finished' || now >= end) return null
  return { label: t('contests.detail.startsIn'), segments: toSegments(start - now) }
})

const ariaLabel = computed(() => {
  if (!countdown.value) return t('contests.detail.contestOver')
  const values = countdown.value.segments.map((segment) => segment.value).join(':')
  return `${countdown.value.label} ${values}`
})
</script>

<template>
  <Popover v-if="countdown">
    <PopoverTrigger as-child>
      <button
        type="button"
        class="flex items-center gap-2.5 rounded-md text-left outline-none transition-colors hover:bg-muted/40 focus-visible:ring-2 focus-visible:ring-ring/50"
        :aria-label="ariaLabel"
        @click.stop
      >
        <span class="text-[11.5px] font-medium uppercase tracking-wide text-muted-foreground">
          {{ countdown.label }}
        </span>
        <span class="flex items-center gap-1">
          <template v-for="(segment, index) in countdown.segments" :key="`${index}-${segment.unit}`">
            <span
              v-if="index > 0"
              class="text-[13px] font-medium text-muted-foreground/60"
              aria-hidden="true"
            >
              :
            </span>
            <span
              class="flex min-w-[30px] flex-col items-center rounded-md border border-border bg-surface px-1.5 py-1"
            >
              <span
                class="text-[16px] font-semibold leading-5 tabular-nums"
                :class="
                  status === 'running' ? TONE_TEXT_CLASSES.success : TONE_TEXT_CLASSES.info
                "
              >
                {{ segment.value }}
              </span>
              <span class="text-[9px] leading-3 text-muted-foreground">{{ segment.unit }}</span>
            </span>
          </template>
        </span>
      </button>
    </PopoverTrigger>
    <PopoverContent align="start" class="w-auto min-w-[220px] p-3">
      <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[12.5px]">
        <dt class="text-muted-foreground">{{ t('contests.detail.startTime') }}</dt>
        <dd class="tabular-nums">{{ formatDateTime(startTime) }}</dd>
        <dt class="text-muted-foreground">{{ t('contests.detail.endTime') }}</dt>
        <dd class="tabular-nums">{{ formatDateTime(endTime) }}</dd>
      </dl>
    </PopoverContent>
  </Popover>
  <span v-else class="text-[12px] text-muted-foreground">{{
    t('contests.detail.contestOver')
  }}</span>
</template>