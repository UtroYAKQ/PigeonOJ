<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { TONE_SURFACE_CLASSES } from '@/components/common/tone'
import type { BoardCell } from '@/types'

const props = defineProps<{
  cell: BoardCell
  /** ACM 赛制：通过格展示罚时；IOI 展示得分 */
  acm: boolean
  /** 全场首次通过（一血） */
  first: boolean
  /** AC 格可点击（赛后 / 管理角色） */
  clickable: boolean
}>()

const emit = defineEmits<{ open: [] }>()
const { t } = useI18n()

const label = computed(() => {
  if (props.acm) {
    if (props.cell.accepted) return String(props.cell.penalty)
    if (props.cell.attempts > 0) return `-${props.cell.attempts}`
    return '·'
  }
  if (props.cell.accepted) return String(props.cell.score)
  if (props.cell.score > 0) return String(props.cell.score)
  if (props.cell.attempts > 0) return `-${props.cell.attempts}`
  return '·'
})

const toneClass = computed(() => {
  if (props.cell.is_frozen) {
    return 'border border-dashed border-border bg-muted text-muted-foreground'
  }
  if (props.cell.accepted) {
    return props.first
      ? 'bg-emerald-600 text-white'
      : TONE_SURFACE_CLASSES.success
  }
  if (!props.acm && props.cell.score > 0) return TONE_SURFACE_CLASSES.info
  if (props.cell.attempts > 0) return TONE_SURFACE_CLASSES.danger
  return 'text-muted-foreground/50'
})

const canOpen = computed(() => props.cell.accepted && !props.cell.is_frozen && props.clickable)

const hint = computed(() => {
  if (props.cell.is_frozen) return t('contests.board.frozenCellHint')
  if (canOpen.value) return t('contests.board.cellClickableHint')
  return undefined
})
</script>

<template>
  <button
    v-if="canOpen"
    type="button"
    class="inline-flex min-w-[40px] cursor-pointer items-center justify-center rounded-full px-2 py-0.5 text-[12.5px] font-semibold tabular-nums transition-opacity hover:opacity-75"
    :class="toneClass"
    :title="hint"
    @click="emit('open')"
  >
    {{ label }}
  </button>
  <span
    v-else
    class="inline-flex min-w-[40px] items-center justify-center rounded-full px-2 py-0.5 text-[12.5px] font-semibold tabular-nums"
    :class="toneClass"
    :title="hint"
  >
    {{ label }}
  </span>
</template>
