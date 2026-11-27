<script setup lang="ts">
/**
 * 用户邮箱搜索选择器：输入完整邮箱 → 查询 → 从结果中选择一个或多个用户。
 * 查询函数由宿主注入（组织成员候选 / 站点用户查找），组件只负责交互与已选集合。
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader2, Search, X } from '@lucide/vue'

import BaseAvatar from './BaseAvatar.vue'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { message } from '@/utils/feedback'
import type { UserCandidate } from '@/types'

const props = defineProps<{
  search: (email: string) => Promise<UserCandidate[]>
  placeholder?: string
}>()

const selected = defineModel<UserCandidate[]>({ default: () => [] })
const { t } = useI18n()

const keyword = ref('')
const results = ref<UserCandidate[]>([])
const searching = ref(false)
const searched = ref(false)

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const selectedIds = computed(() => new Set(selected.value.map((item) => item.id)))

function add(item: UserCandidate): void {
  if (item.disabled || selectedIds.value.has(item.id)) return
  selected.value = [...selected.value, item]
}

function remove(id: string): void {
  selected.value = selected.value.filter((item) => item.id !== id)
}

async function runSearch(): Promise<void> {
  const email = keyword.value.trim()
  if (!EMAIL_RE.test(email)) {
    message.warning(t('userEmailPicker.invalidEmail'))
    return
  }
  searching.value = true
  try {
    results.value = await props.search(email)
    searched.value = true
  } catch (error) {
    results.value = []
    message.error(error instanceof Error ? error.message : t('userEmailPicker.searchFailed'))
  } finally {
    searching.value = false
  }
}
</script>

<template>
  <div class="space-y-3">
    <div class="flex items-start gap-2">
      <Input
        v-model="keyword"
        class="h-9 text-[13px]"
        :placeholder="placeholder ?? t('userEmailPicker.placeholder')"
        @keyup.enter="runSearch"
      />
      <Button
        type="button"
        variant="outline"
        size="toolbar"
        class="shrink-0"
        :disabled="searching"
        @click="runSearch"
      >
        <Loader2 v-if="searching" class="size-4 animate-spin" />
        <Search v-else class="size-4" />
        {{ t('action.search') }}
      </Button>
    </div>

    <p class="text-[12px] leading-5 text-muted-foreground">{{ t('userEmailPicker.hint') }}</p>

    <ul v-if="results.length" class="divide-y divide-border rounded-md border border-border">
      <li v-for="item in results" :key="item.id" class="flex items-center gap-3 px-3 py-2.5">
        <BaseAvatar :src="item.avatar_url" :name="item.nickname" :size="30" />
        <div class="min-w-0 flex-1">
          <p class="truncate text-[13px] font-medium">{{ item.nickname }}</p>
          <p class="truncate text-[12px] text-muted-foreground">{{ item.email }}</p>
          <p v-if="item.disabled && item.note" class="truncate text-[11px] text-muted-foreground">
            {{ item.note }}
          </p>
        </div>
        <Button
          type="button"
          size="xs"
          variant="outline"
          :disabled="item.disabled || selectedIds.has(item.id)"
          @click="add(item)"
        >
          {{ selectedIds.has(item.id) ? t('userEmailPicker.added') : t('userEmailPicker.add') }}
        </Button>
      </li>
    </ul>
    <p v-else-if="searched && !searching" class="text-[12px] text-muted-foreground">
      {{ t('userEmailPicker.empty') }}
    </p>

    <div v-if="selected.length" class="space-y-2">
      <p class="text-[12px] font-medium text-muted-foreground">
        {{ t('userEmailPicker.selected') }}
      </p>
      <div class="flex flex-wrap gap-2">
        <span
          v-for="item in selected"
          :key="item.id"
          class="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted/40 py-1 pl-2.5 pr-1.5 text-[12px]"
          :title="item.email"
        >
          <BaseAvatar :src="item.avatar_url" :name="item.nickname" :size="18" />
          <span class="max-w-[180px] truncate">{{ item.nickname }}</span>
          <button
            type="button"
            class="grid size-4 place-items-center rounded-sm text-muted-foreground hover:bg-muted hover:text-foreground"
            :aria-label="t('userEmailPicker.remove')"
            @click="remove(item.id)"
          >
            <X class="size-3" />
          </button>
        </span>
      </div>
    </div>
  </div>
</template>