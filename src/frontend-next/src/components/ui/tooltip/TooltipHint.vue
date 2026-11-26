<script setup lang="ts">
import type { TooltipContentProps } from 'reka-ui'
import Tooltip from './Tooltip.vue'
import TooltipContent from './TooltipContent.vue'
import TooltipTrigger from './TooltipTrigger.vue'

withDefaults(
  defineProps<{
    text?: string | null
    side?: TooltipContentProps['side']
    align?: TooltipContentProps['align']
    disabled?: boolean
  }>(),
  {
    text: '',
    side: 'top',
    align: 'center',
    disabled: false,
  },
)
</script>

<template>
  <Tooltip v-if="text && !disabled">
    <TooltipTrigger as-child>
      <slot />
    </TooltipTrigger>
    <TooltipContent :side="side" :align="align" :side-offset="6">
      {{ text }}
    </TooltipContent>
  </Tooltip>
  <slot v-else />
</template>
