<script setup lang="ts">
import type { TabsListProps } from 'reka-ui'

import type { HTMLAttributes } from 'vue'
import { reactiveOmit } from '@vueuse/core'
import { cn } from 'cn'
import { TabsList, useForwardProps } from 'reka-ui'

const props = defineProps<TabsListProps & { class?: HTMLAttributes['class'] }>()

const delegatedProps = reactiveOmit(props, 'class')

const forwardedProps = useForwardProps(delegatedProps)
</script>

<template>
  <TabsList
    data-slot="tabs-list"
    v-bind="forwardedProps"
    :class="
      cn(
        'inline-flex h-8 w-fit items-center justify-center rounded-lg bg-muted p-[3px] text-muted-foreground',
        props.class,
      )
    "
  >
    <slot />
  </TabsList>
</template>
