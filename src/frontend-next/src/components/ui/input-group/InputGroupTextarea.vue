<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { useVModel } from '@vueuse/core'
import { cn } from 'cn'

const props = defineProps<{
  modelValue?: string
  class?: HTMLAttributes['class']
}>()

const emits = defineEmits<{
  (e: 'update:modelValue', payload: string): void
}>()

const model = useVModel(props, 'modelValue', emits, {
  passive: true,
  defaultValue: '',
})
</script>

<template>
  <textarea
    v-model="model"
    data-slot="input-group-textarea"
    :class="
      cn(
        'placeholder:text-muted-foreground min-h-[64px] w-full min-w-0 flex-1 resize-none border-0 bg-transparent px-3 py-2 text-[13px] leading-6 outline-none focus:outline-none focus-visible:ring-0 disabled:cursor-not-allowed disabled:opacity-50',
        props.class,
      )
    "
  />
</template>