<script setup lang="ts">
import { Card } from '@/components/ui/card'

defineProps<{ title: string; hint?: string }>()
</script>

<template>
  <Card class="flex flex-col gap-3 p-4">
    <div class="space-y-1">
      <h2 class="text-[13.5px] font-semibold leading-5">{{ title }}</h2>
      <p v-if="hint" class="text-[12px] leading-5 text-muted-foreground">{{ hint }}</p>
    </div>
    <slot />
    <slot name="footer" />
  </Card>
</template>
