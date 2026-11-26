<script setup lang="ts">
import { Badge } from '@/components/ui/badge'
import {
  TONE_BADGE_CLASSES,
  TONE_DOT_CLASSES,
  type Tone,
} from '@/components/common/tone'

withDefaults(
  defineProps<{
    tone: Tone
    label: string
    /** 状态类徽标：色点 + 文本，避免单靠颜色传递语义 */
    dot?: boolean
    /** 进行中状态：色点呼吸 */
    pulse?: boolean
  }>(),
  { dot: false, pulse: false },
)
</script>

<template>
  <Badge
    variant="outline"
    class="h-5 border px-2 text-[11.5px] font-medium"
    :class="[TONE_BADGE_CLASSES[tone], dot ? 'gap-1.5' : '']"
  >
    <span
      v-if="dot"
      class="size-1.5 shrink-0 rounded-full"
      :class="[TONE_DOT_CLASSES[tone], pulse ? 'animate-pulse' : '']"
      aria-hidden="true"
    />
    {{ label }}
  </Badge>
</template>