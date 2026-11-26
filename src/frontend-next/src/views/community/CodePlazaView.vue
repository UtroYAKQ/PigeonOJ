<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { PenLine } from '@lucide/vue'

import { listCodeShares } from '@/api/community'
import FilterCheckbox from '@/components/common/FilterCheckbox.vue'
import PaginatedCardGrid from '@/components/common/PaginatedCardGrid.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import CodeShareCard from '@/components/community/CodeShareCard.vue'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { languageOptions } from '@/constants/languages'
import { usePagination } from '@/composables/usePagination'
import { useUserStore } from '@/stores/user'
import { message } from '@/utils/feedback'
import type { CodeShareLanguage, CodeShareSummary } from '@/types'

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const shares = ref<CodeShareSummary[]>([])
const loading = ref(false)
const keyword = ref('')
const language = ref<'all' | CodeShareLanguage>('all')
const mineOnly = ref(false)
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await listCodeShares({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      language: language.value === 'all' ? undefined : language.value,
      mine: mineOnly.value || undefined,
    })
    if (!isCurrent(seq)) return
    shares.value = result.items
    total.value = result.total
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

function onSearch(): void {
  resetPage()
  void load()
}

function onMineChange(value: boolean): void {
  mineOnly.value = value
  onSearch()
}

function onPageChange(value: number): void {
  changePage(value)
  void load()
}

function openShare(share: CodeShareSummary): void {
  void router.push(`/codes/${share.id}`)
}

onMounted(load)
</script>

<template>
  <WorkbenchShell :title="t('nav.codePlaza')">
    <template #toolbar>
      <SearchFilterBar
        :keyword="keyword"
        :placeholder="t('codes.searchPlaceholder')"
        @update:keyword="keyword = $event"
        @search="onSearch"
        @reset="onSearch"
      >
        <Select
          :model-value="language"
          @update:model-value="
            (value) => {
              language = value as typeof language
              onSearch()
            }
          "
        >
          <SelectTrigger class="h-9 w-[150px] text-[13px]">
            <SelectValue :placeholder="t('codes.languageLabel')" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{{ t('codes.allLanguages') }}</SelectItem>
            <SelectItem v-for="option in languageOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </SelectItem>
          </SelectContent>
        </Select>
        <template #actions>
          <FilterCheckbox
            v-if="userStore.isLoggedIn"
            id="codes-mine"
            :model-value="mineOnly"
            :label="t('codes.mineOnly')"
            @update:model-value="onMineChange"
          />
          <Button v-if="userStore.isLoggedIn" size="toolbar" @click="router.push('/codes/new')">
            <PenLine class="size-4" />
            {{ t('codes.share') }}
          </Button>
          <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
        </template>
      </SearchFilterBar>
    </template>

    <PaginatedCardGrid
      :items="shares"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :empty-text="t(mineOnly ? 'codes.mineEmpty' : 'codes.empty')"
      @update:page="onPageChange"
    >
      <template #default="{ item }">
        <CodeShareCard :share="item" @open="openShare" />
      </template>
    </PaginatedCardGrid>
  </WorkbenchShell>
</template>
