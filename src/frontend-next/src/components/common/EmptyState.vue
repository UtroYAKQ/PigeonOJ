<script setup lang="ts">
import type { Component } from 'vue'
import { Inbox } from '@lucide/vue'

withDefaults(defineProps<{ text: string; icon?: Component }>(), { icon: () => Inbox })
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-2 text-center text-muted-foreground">
    <component :is="icon" class="size-7" :stroke-width="1.5" aria-hidden="true" />
    <p class="text-sm">{{ text }}</p>
    <slot />
  </div>
</template>