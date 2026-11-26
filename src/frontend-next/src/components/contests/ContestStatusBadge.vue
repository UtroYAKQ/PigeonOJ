<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import ToneBadge from '@/components/common/ToneBadge.vue'
import type { Tone } from '@/components/common/tone'
import type { ContestStatusType } from '@/types'

const props = defineProps<{ status: ContestStatusType }>()
const { t } = useI18n()

const meta = computed<{ label: string; tone: Tone; pulse: boolean }>(() => {
  if (props.status === 'running') {
    return { label: t('contests.statusRunning'), tone: 'success', pulse: true }
  }
  if (props.status === 'finished') {
    return { label: t('contests.statusFinished'), tone: 'default', pulse: false }
  }
  return { label: t('contests.statusScheduled'), tone: 'info', pulse: false }
})
</script>

<template>
  <ToneBadge :tone="meta.tone" :label="meta.label" dot :pulse="meta.pulse" />
</template>