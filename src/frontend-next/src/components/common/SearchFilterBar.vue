<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Search as SearchIcon, X } from '@lucide/vue'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

withDefaults(
  defineProps<{
    keyword?: string
    placeholder?: string
    searchWidth?: string
    showSearch?: boolean
  }>(),
  { searchWidth: '260px', showSearch: true },
)

const emit = defineEmits<{
  'update:keyword': [value: string]
  search: []
  reset: []
}>()

const { t } = useI18n()

function onInput(event: Event): void {
  emit('update:keyword', (event.target as HTMLInputElement).value)
  if (!(event.target as HTMLInputElement).value) emit('reset')
}

function clear(): void {
  emit('update:keyword', '')
  emit('reset')
}
</script>

<template>
  <div class="flex flex-wrap items-center gap-2">
    <div
      v-if="showSearch"
      class="relative w-full shrink-0 sm:w-[var(--sf-search-w)]"
      :style="{ '--sf-search-w': searchWidth }"
    >
      <SearchIcon
        class="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
      />
      <Input
        :model-value="keyword"
        class="h-9 pl-8 pr-8 text-[13px]"
        :placeholder="placeholder"
        @input="onInput"
        @keyup.enter="$emit('search')"
      />
      <button
        v-if="keyword"
        type="button"
        class="absolute right-0 top-1/2 grid h-9 w-8 -translate-y-1/2 place-items-center text-muted-foreground transition-colors hover:text-foreground"
        :aria-label="t('action.clearSearch')"
        @click="clear"
      >
        <X class="size-3.5" />
      </button>
    </div>
    <slot />
    <Button v-if="showSearch" size="toolbar" @click="$emit('search')">
      {{ t('action.search') }}
    </Button>
    <div class="flex-1" />
    <slot name="actions" />
  </div>
</template>
