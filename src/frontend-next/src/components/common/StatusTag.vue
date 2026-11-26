<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { Badge } from '@/components/ui/badge'
import { TONE_BADGE_CLASSES, type Tone } from '@/components/common/tone'

const props = defineProps<{ status: string }>()
const { t } = useI18n()

const tone = computed<Tone>(() => {
  if (props.status === 'accepted' || props.status === 'ok') return 'success'
  if (props.status === 'pending' || props.status === 'judging') return 'info'
  if (props.status === 'wrong_answer') return 'warning'
  if (props.status === 'compile_error') return 'violet'
  return 'danger'
})
</script>

<template>
  <Badge
    variant="outline"
    class="h-5 border px-2 text-[11.5px] font-medium"
    :class="TONE_BADGE_CLASSES[tone]"
  >
    {{ t(`problems.status.${status}`) }}
  </Badge>
</template>