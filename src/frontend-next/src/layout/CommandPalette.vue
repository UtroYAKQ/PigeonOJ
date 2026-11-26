<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Search } from '@lucide/vue'

import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'

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

const query = ref('')
const activeIndex = ref(0)
const inputRef = ref<HTMLInputElement | null>(null)
const listRef = ref<HTMLElement | null>(null)

const filtered = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  if (!keyword) return props.items
  return props.items.filter((item) => `${item.label} ${item.group}`.toLowerCase().includes(keyword))
})

const grouped = computed(() => {
  const order: string[] = []
  const groups = new Map<string, CommandItem[]>()
  for (const item of filtered.value) {
    if (!groups.has(item.group)) {
      groups.set(item.group, [])
      order.push(item.group)
    }
    groups.get(item.group)!.push(item)
  }
  return order.map((group) => ({ group, items: groups.get(group)! }))
})

const flat = computed(() => grouped.value.flatMap((group) => group.items))

watch(open, async (value) => {
  if (!value) return
  query.value = ''
  activeIndex.value = 0
  await nextTick()
  inputRef.value?.focus()
})

watch(query, () => {
  activeIndex.value = 0
})

function move(delta: number): void {
  if (!flat.value.length) return
  activeIndex.value = (activeIndex.value + delta + flat.value.length) % flat.value.length
  void nextTick(() => {
    listRef.value
      ?.querySelector<HTMLElement>(`[data-command-index="${activeIndex.value}"]`)
      ?.scrollIntoView({ block: 'nearest' })
  })
}

function choose(item: CommandItem | undefined): void {
  if (!item) return
  open.value = false
  item.run()
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    move(1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    move(-1)
  } else if (event.key === 'Enter') {
    event.preventDefault()
    choose(flat.value[activeIndex.value])
  }
}
</script>

<template>
  <Dialog v-model:open="open">
    <DialogContent
      :show-close-button="false"
      class="top-[16%] w-[calc(100%-2rem)] max-w-[560px] translate-y-0 gap-0 overflow-hidden p-0 sm:max-w-[560px]"
    >
      <DialogTitle class="sr-only">{{ t('app.searchMenu') }}</DialogTitle>
      <DialogDescription class="sr-only">{{ t('app.searchMenuPlaceholder') }}</DialogDescription>

      <div class="flex items-center gap-2 border-b border-border px-4">
        <Search class="size-4 shrink-0 text-muted-foreground" />
        <input
          ref="inputRef"
          v-model="query"
          type="text"
          :placeholder="t('app.searchMenuPlaceholder')"
          class="h-12 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          @keydown="onKeydown"
        />
        <span
          class="rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground"
          >Esc</span
        >
      </div>

      <div ref="listRef" class="max-h-[400px] overflow-y-auto p-2">
        <p v-if="!grouped.length" class="px-3 py-10 text-center text-sm text-muted-foreground">
          {{ t('app.noMatchingMenu') }}
        </p>
        <template v-for="group in grouped" :key="group.group">
          <p class="px-2 pb-1 pt-2 text-[11px] font-medium text-muted-foreground">
            {{ group.group }}
          </p>
          <button
            v-for="item in group.items"
            :key="item.key"
            type="button"
            :data-command-index="flat.indexOf(item)"
            class="flex w-full items-center gap-3 rounded-md px-2 py-2 text-left text-sm transition-colors"
            :class="
              flat.indexOf(item) === activeIndex
                ? 'bg-muted text-foreground'
                : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
            "
            @mouseenter="activeIndex = flat.indexOf(item)"
            @click="choose(item)"
          >
            <component
              :is="item.icon"
              v-if="item.icon"
              class="size-4 shrink-0"
              :stroke-width="1.8"
            />
            <span class="min-w-0 flex-1 truncate">{{ item.label }}</span>
          </button>
        </template>
      </div>

      <div
        class="flex items-center justify-between gap-3 border-t border-border bg-popover px-4 py-2 text-[11px] text-muted-foreground"
      >
        <span>{{ t('app.commandHint') }}</span>
        <span>{{ t('app.commandCount', { count: filtered.length }) }}</span>
      </div>
    </DialogContent>
  </Dialog>
</template>
