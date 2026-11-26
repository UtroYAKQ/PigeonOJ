<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { listActiveTags, listProblems } from '@/api/problems'
import FilterCheckbox from '@/components/common/FilterCheckbox.vue'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'

import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { usePagination } from '@/composables/usePagination'
import { useUserStore } from '@/stores/user'
import { message } from '@/utils/feedback'

import type { ProblemSummary, ProblemTagItem } from '@/types'

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const loading = ref(false)
const problems = ref<ProblemSummary[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()

const keyword = ref('')
const tag = ref('all')
const difficultyMin = ref<string | number>('')
const difficultyMax = ref<string | number>('')
const mineOnly = ref(false)
const tagOptions = ref<ProblemTagItem[]>([])

/** 标签列展示偏好：本地持久化，默认展示 */
const SHOW_TAGS_STORAGE_KEY = 'pigeonoj.problems.showTags'

function readShowTags(): boolean {
  try {
    return localStorage.getItem(SHOW_TAGS_STORAGE_KEY) !== '0'
  } catch {
    return true
  }
}

const showTags = ref(readShowTags())

function onToggleTags(value: boolean): void {
  showTags.value = value
  try {
    localStorage.setItem(SHOW_TAGS_STORAGE_KEY, value ? '1' : '0')
  } catch {
    /* 持久化不可用时仅保留当前会话状态 */
  }
}

function onToggleMine(value: boolean): void {
  mineOnly.value = value
  onSearch()
}

const isManager = computed(() => userStore.isAdmin)

function numeric(value: string | number): number | undefined {
  if (value === '') return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : undefined
}

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await listProblems({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      tag: tag.value === 'all' ? undefined : tag.value,
      mine: mineOnly.value || undefined,
      difficulty_min: numeric(difficultyMin.value),
      difficulty_max: numeric(difficultyMax.value),
    })
    if (!isCurrent(seq)) return
    problems.value = result.items
    total.value = result.total
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('problems.list.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

async function loadTags(): Promise<void> {
  try {
    tagOptions.value = await listActiveTags()
  } catch {
    /* 标签加载失败不阻塞列表 */
  }
}

function onSearch(): void {
  resetPage()
  void load()
}

function passRate(row: ProblemSummary): string {
  const count = row.submission_count ?? 0
  if (!count) return '--'
  return `${Math.round(((row.accepted_count ?? 0) / count) * 100)}%`
}

onMounted(() => {
  void load()
  void loadTags()
})

const columns = computed<AppTableColumn<ProblemSummary>[]>(() => {
  const list: AppTableColumn<ProblemSummary>[] = [
    {
      key: 'title',
      title: t('problems.list.name'),
      cell: (row) => row.title,
      cellClass: 'font-medium text-[13.5px]',
    },
  ]

  if (showTags.value) {
    list.push({
      key: 'tags',
      title: t('problems.list.tags'),
      width: '220px',
      cell: (row) => (row.tags ?? []).map((tagItem) => tagItem.name).join(' / ') || '--',
      cellClass: 'text-[12.5px] text-muted-foreground',
    })
  }

  list.push(
    {
      key: 'limits',
      title: t('problems.list.limits'),
      width: '170px',
      cell: (row) => `${row.time_limit_ms} ms / ${row.memory_limit_mb} MB`,
      cellClass: 'tabular-nums text-[12.5px] text-muted-foreground',
    },
    {
      key: 'difficulty',
      title: t('problems.list.difficulty'),
      width: '90px',
      align: 'center',
      cell: (row) => row.difficulty ?? '--',
      cellClass: 'tabular-nums text-[12.5px] text-muted-foreground',
    },
    {
      key: 'passRate',
      title: t('problems.list.passRate'),
      width: '100px',
      align: 'right',
      cell: (row) => passRate(row),
      cellClass: 'tabular-nums text-[12.5px] text-muted-foreground',
    },
  )

  return list
})
</script>

<template>
  <WorkbenchShell :title="t('nav.problems')">
    <template #toolbar>
      <SearchFilterBar
        :keyword="keyword"
        :placeholder="t('problems.list.search')"
        search-width="300px"
        @update:keyword="keyword = $event"
        @search="onSearch"
        @reset="onSearch"
      >
        <Select v-model="tag" @update:model-value="onSearch">
          <SelectTrigger class="h-9 w-[154px] text-[13px]">
            <SelectValue :placeholder="t('problems.list.allTags')" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{{ t('problems.list.allTags') }}</SelectItem>
            <SelectItem v-for="item in tagOptions" :key="item.id" :value="item.name">
              {{ item.name }}
            </SelectItem>
          </SelectContent>
        </Select>

        <div class="flex items-center gap-1.5">
          <Input
            v-model="difficultyMin"
            type="number"
            min="0"
            :placeholder="t('problems.list.difficultyMin')"
            class="h-9 w-[100px] text-[12.5px]"
          />
          <span class="text-muted-foreground">—</span>
          <Input
            v-model="difficultyMax"
            type="number"
            min="0"
            :placeholder="t('problems.list.difficultyMax')"
            class="h-9 w-[100px] text-[12.5px]"
          />
        </div>

        <template #actions>
          <FilterCheckbox
            :model-value="showTags"
            :label="t('problems.list.showTags')"
            @update:model-value="onToggleTags"
          />
          <FilterCheckbox
            v-if="isManager"
            :model-value="mineOnly"
            :label="t('problems.list.mineOnly')"
            @update:model-value="onToggleMine"
          />
          <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
        </template>
      </SearchFilterBar>
    </template>

    <PaginatedTable
      :columns="columns"
      :data="problems"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      :empty-text="t('problems.list.empty')"
      :row-click="(row: ProblemSummary) => router.push(`/problems/${row.id}`)"
      @update:page="
        (value: number) => {
          changePage(value)
          load()
        }
      "
      @update:page-size="
        (value: number) => {
          changeSize(value)
          load()
        }
      "
    >
      <template #pager-left>
        <span class="tabular-nums">{{ t('problems.list.totalCount', { count: total }) }}</span>
      </template>
    </PaginatedTable>
  </WorkbenchShell>
</template>
