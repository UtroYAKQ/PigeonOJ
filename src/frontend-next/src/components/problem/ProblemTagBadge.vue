<script setup lang="ts">
import { Badge } from '@/components/ui/badge'
import type { ProblemTagItem } from '@/types'

defineProps<{ tag: ProblemTagItem }>()
</script>

<template>
  <Badge
    variant="outline"
    class="h-5 rounded-md px-1.5 text-[11.5px] font-normal text-muted-foreground"
    :style="tag.color ? { borderColor: `${tag.color}55`, color: tag.color } : undefined"
  >
    {{ tag.name }}
  </Badge>
</template>