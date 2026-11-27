<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ChevronDown, ChevronUp, GripVertical, Trash2 } from '@lucide/vue'

import LineList from '@/components/common/LineList.vue'
import { Button } from '@/components/ui/button'
import type { ProblemSetItem } from '@/types'

const props = withDefaults(
  defineProps<{
    items: ProblemSetItem[]
    disabled?: boolean
    emptyText?: string
  }>(),
  { disabled: false, emptyText: '' },
)

const emit = defineEmits<{
  move: [index: number, delta: number]
  remove: [item: ProblemSetItem]
  reorder: [from: number, to: number]
}>()

const { t } = useI18n()

/** 原生 HTML5 拖拽（零依赖）：拖起行半透明，目标行顶部插入线指示落点 */
const dragIndex = ref<number | null>(null)
const overIndex = ref<number | null>(null)

function resetDrag(): void {
  dragIndex.value = null
  overIndex.value = null
}

function onDragStart(index: number, event: Event): void {
  if (props.disabled) return
  const dragEvent = event as DragEvent
  dragIndex.value = index
  if (dragEvent.dataTransfer) {
    // dataTransfer 必须写入数据，否则 Firefox 不触发 dragover / drop
    dragEvent.dataTransfer.effectAllowed = 'move'
    dragEvent.dataTransfer.setData('text/plain', String(index))
  }
}

function onDragOver(index: number, event: Event): void {
  if (props.disabled || dragIndex.value === null) return
  event.preventDefault()
  const dragEvent = event as DragEvent
  if (dragEvent.dataTransfer) dragEvent.dataTransfer.dropEffect = 'move'
  if (overIndex.value !== index) overIndex.value = index
}

function onDrop(index: number): void {
  if (props.disabled || dragIndex.value === null) {
    resetDrag()
    return
  }
  const from = dragIndex.value
  resetDrag()
  if (from !== index) emit('reorder', from, index)
}

watch(
  () => props.disabled,
  (disabled) => {
    if (disabled) resetDrag()
  },
)

function limits(item: ProblemSetItem): string {
  return `${item.time_limit_ms ?? '--'} ms / ${item.memory_limit_mb ?? '--'} MB`
}

function difficulty(item: ProblemSetItem): string {
  return (item.difficulty ?? null) === null ? '--' : String(item.difficulty)
}
</script>

<template>
  <LineList :items="items" :empty-text="emptyText || t('problemSets.detail.empty')">
    <template #header>
      <div
        class="grid min-h-10 items-center gap-3 px-3 py-2 text-xs font-medium text-muted-foreground"
        style="grid-template-columns: 60px minmax(0, 1fr) 80px 150px 124px"
      >
        <span>{{ t('problemSets.detail.orderLabel') }}</span>
        <span>{{ t('problemSets.list.titleLabel') }}</span>
        <span>{{ t('problemSets.detail.difficulty') }}</span>
        <span>{{ t('problems.list.limits') }}</span>
        <span />
      </div>
    </template>

    <template #item="{ item, index }">
      <div
        class="grid w-full items-center gap-3 px-3 py-2.5"
        style="grid-template-columns: 60px minmax(0, 1fr) 80px 150px 124px"
        :draggable="!disabled"
        :class="[
          !disabled ? 'cursor-grab' : '',
          dragIndex === index ? 'opacity-40' : '',
          overIndex === index && dragIndex !== null
            ? 'shadow-[inset_0_2px_0_0_var(--primary)]'
            : '',
        ]"
        @dragstart="onDragStart(index, $event)"
        @dragover="onDragOver(index, $event)"
        @drop.prevent="onDrop(index)"
        @dragend="resetDrag"
      >
        <span class="inline-flex items-center gap-1 text-[12px] tabular-nums text-muted-foreground">
          <GripVertical class="size-3.5 text-muted-foreground/60" aria-hidden="true" />
          {{ index + 1 }}
        </span>
        <span class="min-w-0 truncate text-[13px] font-medium">{{ item.title }}</span>
        <span class="text-[12.5px] tabular-nums text-muted-foreground">{{ difficulty(item) }}</span>
        <span class="text-[12.5px] tabular-nums text-muted-foreground">{{ limits(item) }}</span>
        <span class="flex items-center justify-end gap-0.5">
          <Button
            variant="ghost"
            size="icon-xs"
            :disabled="disabled || index === 0"
            :aria-label="t('action.moveUp')"
            @click.stop="emit('move', index, -1)"
          >
            <ChevronUp class="size-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon-xs"
            :disabled="disabled || index === items.length - 1"
            :aria-label="t('action.moveDown')"
            @click.stop="emit('move', index, 1)"
          >
            <ChevronDown class="size-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon-xs"
            class="text-destructive hover:bg-destructive/10 hover:text-destructive"
            :disabled="disabled"
            :aria-label="t('problemSets.detail.remove')"
            @click.stop="emit('remove', item)"
          >
            <Trash2 class="size-3.5" />
          </Button>
        </span>
      </div>
    </template>
  </LineList>
</template>
