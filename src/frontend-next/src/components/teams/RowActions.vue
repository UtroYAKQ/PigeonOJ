<script setup lang="ts">
import { Ellipsis } from '@lucide/vue'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { RowAction } from './types'

defineProps<{
  actions: RowAction[]
  /** 触发按钮无障碍名称（如「更多操作」） */
  label: string
}>()

const emit = defineEmits<{
  select: [key: string]
}>()
</script>

<template>
  <DropdownMenu>
    <DropdownMenuTrigger as-child>
      <Button
        variant="ghost"
        size="icon-sm"
        class="size-7 text-muted-foreground"
        :aria-label="label"
        @click.stop
      >
        <Ellipsis class="size-4" />
      </Button>
    </DropdownMenuTrigger>
    <DropdownMenuContent align="end" class="w-40" @click.stop>
      <DropdownMenuItem
        v-for="action in actions"
        :key="action.key"
        :disabled="action.disabled"
        :variant="action.destructive ? 'destructive' : 'default'"
        @select="emit('select', action.key)"
      >
        {{ action.label }}
      </DropdownMenuItem>
    </DropdownMenuContent>
  </DropdownMenu>
</template>
