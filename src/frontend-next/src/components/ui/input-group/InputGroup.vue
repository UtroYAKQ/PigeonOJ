<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { cn } from 'cn'

const props = defineProps<{ class?: HTMLAttributes['class'] }>()
</script>

<template>
  <div
    data-slot="input-group"
    role="group"
    :class="
      cn(
        'dark:bg-input/30 border-input focus-within:border-ring focus-within:ring-ring/50 relative flex w-full items-center rounded-md border bg-transparent shadow-xs transition-[color,box-shadow] focus-within:ring-3',
        props.class,
      )
    "
  >
    <slot />
  </div>
</template>