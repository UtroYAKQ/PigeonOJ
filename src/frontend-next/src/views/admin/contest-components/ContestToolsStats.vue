<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Copy } from '@lucide/vue'

import { Button } from '@/components/ui/button'
import { formatDateTime } from '@/utils/format'
import type { ContestDetail } from '@/types'

const props = defineProps<{ contest: ContestDetail }>()

defineEmits<{ copy: [] }>()

const { t } = useI18n()

const nowTick = ref(Date.now())
let clockTimer: number | null = null

function pad(value: number): string {
  return String(value).padStart(2, '0')
}

function formatRemain(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const days = Math.floor(total / 86400)
  const hours = Math.floor((total % 86400) / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  if (days > 0) {
    return `${days}${t('contests.detail.unitDay')} ${pad(hours)}:${pad(minutes)}:${pad(seconds)}`
  }
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`
}

const countdown = computed(() => {
  const detail = props.contest
  const now = nowTick.value
  const start = new Date(detail.start_time).getTime()
  const end = new Date(detail.end_time).getTime()
  if (detail.status === 'finished' || now >= end) {
    return { label: t('contests.detail.contestOver'), value: '—' }
  }
  if (detail.status === 'running' || now >= start) {
    return { label: t('contests.detail.endsIn'), value: formatRemain(end - now) }
  }
  return { label: t('contests.detail.startsIn'), value: formatRemain(start - now) }
})

onMounted(() => {
  clockTimer = window.setInterval(() => {
    nowTick.value = Date.now()
  }, 1000)
})

onBeforeUnmount(() => {
  if (clockTimer !== null) window.clearInterval(clockTimer)
})
</script>

<template>
  <section
    class="grid shrink-0 gap-3 rounded-lg border border-border bg-muted/30 p-3 sm:grid-cols-2 xl:grid-cols-5"
  >
    <div class="min-w-0 space-y-0.5">
      <p class="text-[11.5px] text-muted-foreground">{{ countdown.label }}</p>
      <p class="text-[18px] font-semibold leading-6 tabular-nums tracking-wide">
        {{ countdown.value }}
      </p>
    </div>
    <div class="min-w-0 space-y-0.5">
      <p class="text-[11.5px] text-muted-foreground">{{ t('contests.detail.registeredCount') }}</p>
      <p class="text-[18px] font-semibold leading-6 tabular-nums">{{ contest.registered_count }}</p>
    </div>
    <div class="min-w-0 space-y-0.5">
      <p class="text-[11.5px] text-muted-foreground">{{ t('contests.detail.problems') }}</p>
      <p class="text-[18px] font-semibold leading-6 tabular-nums">{{ contest.problem_count }}</p>
    </div>
    <div class="min-w-0 space-y-0.5">
      <p class="text-[11.5px] text-muted-foreground">{{ t('contests.tools.freezeAt') }}</p>
      <p class="text-[13px] font-semibold leading-6 tabular-nums">
        {{
          contest.freeze_time ? formatDateTime(contest.freeze_time) : t('contests.tools.noFreeze')
        }}
      </p>
    </div>
    <div class="flex items-end xl:items-center">
      <Button variant="outline" size="sm" @click="$emit('copy')">
        <Copy class="size-3.5" />
        {{ t('contests.tools.copyLink') }}
      </Button>
    </div>
  </section>
</template>
