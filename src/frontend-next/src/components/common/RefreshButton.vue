<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { RefreshCw } from '@lucide/vue'

import { Button } from '@/components/ui/button'
import { TooltipHint } from '@/components/ui/tooltip'

const props = defineProps<{ loading?: boolean; label?: string }>()
// Tooltip 链（TooltipHint → TooltipRoot → PopperRoot）不渲染 DOM 元素，
// 外部 @click 靠 attrs 透传会在中途丢失；显式声明并转发到按钮。
const emit = defineEmits<{ click: [event: MouseEvent] }>()
const { t } = useI18n()
const tip = computed(() => props.label ?? t('action.refresh'))

function onClick(event: MouseEvent): void {
  emit('click', event)
}
</script>

<template>
  <TooltipHint :text="tip">
    <Button variant="ghost" size="icon-sm" :aria-label="tip" @click="onClick">
      <RefreshCw class="size-4" :class="{ 'animate-spin': loading }" />
    </Button>
  </TooltipHint>
</template>
