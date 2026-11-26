<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem as CommandItemRow,
  CommandList,
} from '@/components/ui/command'

export interface CommandItem {
  key: string
  label: string
  group: string
  icon?: unknown
  run: () => void
}

const props = defineProps<{ items: CommandItem[] }>()
const { t } = useI18n()
const open = defineModel<boolean>('open', { required: true })

const grouped = computed(() => {
  const order: string[] = []
  const groups = new Map<string, CommandItem[]>()
  for (const item of props.items) {
    if (!groups.has(item.group)) {
      groups.set(item.group, [])
      order.push(item.group)
    }
    groups.get(item.group)!.push(item)
  }
  return order.map((group) => ({ group, items: groups.get(group)! }))
})

function choose(item: CommandItem): void {
  open.value = false
  item.run()
}
</script>

<template>
  <CommandDialog v-model:open="open">
    <CommandInput :placeholder="t('app.searchMenuPlaceholder')" />
    <CommandList>
      <CommandEmpty>{{ t('app.noMatchingMenu') }}</CommandEmpty>
      <CommandGroup v-for="group in grouped" :key="group.group" :heading="group.group">
        <CommandItemRow
          v-for="item in group.items"
          :key="item.key"
          :value="item.key"
          @select="choose(item)"
        >
          <component :is="item.icon" v-if="item.icon" :stroke-width="1.8" />
          <span class="min-w-0 flex-1 truncate">{{ item.label }}</span>
        </CommandItemRow>
      </CommandGroup>
    </CommandList>
  </CommandDialog>
</template>
