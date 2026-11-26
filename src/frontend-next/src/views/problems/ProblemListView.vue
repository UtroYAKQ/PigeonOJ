<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { listActiveTags, listProblems } from '@/api/problems'
import FilterCheckbox from '@/components/common/FilterCheckbox.vue'
import LineList from '@/components/common/LineList.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import VNodeContent from '@/components/common/VNodeContent'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
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
import { renderSolveMark } from '@/utils/solveMark'
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

function renderTag(item: ProblemTagItem) {
  return h(
    'span',
    {
      class:
        'inline-flex h-4.5 items-center rounded border border-border px-1.5 text-[11px] text-muted-foreground',
      style: item.color ? { color: item.color, borderColor: `${item.color}55` } : undefined,
      title: item.name,
    },
    item.name,
  )
}

const gridClass = computed(() =>
  showTags.value
    ? 'grid-cols-[56px_minmax(0,1fr)_220px_170px_90px_100px]'
    : 'grid-cols-[56px_minmax(0,1fr)_170px_90px_100px]',
)

function visibleTags(row: ProblemSummary) {
  const tags = row.tags ?? []
  return { visible: tags.slice(0, 4), rest: tags.slice(4) }
}
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

    <LineList
      :items="problems"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :show-pager="true"
      :empty-text="t('problems.list.empty')"
      min-width="900px"
      :get-key="(row: ProblemSummary) => row.id"
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
      <template #header>
        <div
          class="grid items-center gap-4 px-3 pb-2 text-xs font-medium text-muted-foreground"
          :class="gridClass"
        >
          <span class="sr-only">{{ t('problems.list.solveNever') }}</span>
          <span>{{ t('problems.list.name') }}</span>
          <span v-if="showTags">{{ t('problems.list.tags') }}</span>
          <span>{{ t('problems.list.limits') }}</span>
          <span class="text-center">{{ t('problems.list.difficulty') }}</span>
          <span class="text-right">{{ t('problems.list.passRate') }}</span>
        </div>
      </template>

      <template #skeleton>
        <div
          v-for="row in 6"
          :key="row"
          class="grid items-center gap-4 px-3 py-4"
          :class="gridClass"
        >
          <span class="size-4 rounded bg-muted" />
          <span class="h-4 w-2/5 rounded bg-muted" />
          <span v-if="showTags" class="h-3.5 w-3/4 rounded bg-muted/70" />
          <span class="h-3.5 w-4/5 rounded bg-muted/70" />
          <span class="h-3.5 w-8 justify-self-center rounded bg-muted/70" />
          <span class="h-3.5 w-10 justify-self-end rounded bg-muted/70" />
        </div>
      </template>

      <template #item="{ item }">
        <button
          type="button"
          class="grid w-full items-center gap-4 px-3 py-3.5 text-left transition-colors focus-visible:bg-muted/40 focus-visible:outline-none"
          :class="gridClass"
          @click="router.push(`/problems/${item.id}`)"
        >
          <span class="grid place-items-center">
            <VNodeContent :node="renderSolveMark(t, item.solved)" />
          </span>

          <span class="flex min-w-0 flex-wrap items-center gap-2">
            <span class="truncate text-sm font-semibold text-foreground">{{ item.title }}</span>
            <ToneBadge
              v-if="item.visibility === 'private'"
              tone="danger"
              :label="t('problems.list.privateTag')"
            />
          </span>

          <span v-if="showTags" class="flex min-w-0 flex-wrap items-center gap-1">
            <VNodeContent
              v-for="tagItem in visibleTags(item).visible"
              :key="tagItem.id"
              :node="renderTag(tagItem)"
            />
            <span
              v-if="visibleTags(item).rest.length"
              class="text-xs text-muted-foreground"
              :title="
                visibleTags(item)
                  .rest.map((tagItem) => tagItem.name)
                  .join(', ')
              "
            >
              +{{ visibleTags(item).rest.length }}
            </span>
          </span>

          <span class="text-sm text-muted-foreground tabular-nums">
            {{ item.time_limit_ms }} ms / {{ item.memory_limit_mb }} MB
          </span>
          <span class="text-center text-sm text-muted-foreground tabular-nums">
            {{ item.difficulty ?? '--' }}
          </span>
          <span class="text-right text-sm text-muted-foreground tabular-nums">
            {{ passRate(item) }}
          </span>
        </button>
      </template>

      <template #pager-left>
        <span class="tabular-nums">{{ t('problems.list.totalCount', { count: total }) }}</span>
      </template>
    </LineList>
  </WorkbenchShell>
</template>
