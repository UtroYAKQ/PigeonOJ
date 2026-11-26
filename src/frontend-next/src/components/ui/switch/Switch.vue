<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import type { SwitchRootEmits, SwitchRootProps } from 'reka-ui'
import { reactiveOmit } from '@vueuse/core'
import { cn } from 'cn'
import { SwitchRoot, SwitchThumb, useForwardPropsEmits } from 'reka-ui'

const props = defineProps<SwitchRootProps & { class?: HTMLAttributes['class'] }>()
const emits = defineEmits<SwitchRootEmits>()

const delegatedProps = reactiveOmit(props, 'class')
const forwarded = useForwardPropsEmits(delegatedProps, emits)
</script>

<template>
  <SwitchRoot
    data-slot="switch"
    v-bind="forwarded"
    :class="
      cn(
        'peer inline-flex h-6 w-10 shrink-0 items-center rounded-full border border-transparent transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=unchecked]:bg-input',
        props.class,
      )
    "
  >
    <SwitchThumb
      data-slot="switch-thumb"
      class="pointer-events-none block size-5 rounded-full border border-border/70 bg-background ring-0 transition-transform data-[state=checked]:translate-x-[18px] data-[state=unchecked]:translate-x-0.5"
    />
  </SwitchRoot>
</template>
