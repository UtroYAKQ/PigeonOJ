<script setup lang="ts">
import type { TabsContentProps } from 'reka-ui'

import type { HTMLAttributes } from 'vue'
import { reactiveOmit } from '@vueuse/core'
import { cn } from 'cn'
import { TabsContent, useForwardProps } from 'reka-ui'

const props = defineProps<TabsContentProps & { class?: HTMLAttributes['class'] }>()

const delegatedProps = reactiveOmit(props, 'class')

const forwardedProps = useForwardProps(delegatedProps)
</script>

<template>
  <TabsContent
    data-slot="tabs-content"
    v-bind="forwardedProps"
    :class="cn('flex-1 outline-none data-[state=inactive]:hidden', props.class)"
  >
    <slot />
  </TabsContent>
</template>
