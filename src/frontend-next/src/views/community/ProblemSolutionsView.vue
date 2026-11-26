<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, PenLine } from '@lucide/vue'

import { getEditorial, listSolutions } from '@/api/community'
import FilterCheckbox from '@/components/common/FilterCheckbox.vue'
import MarkdownView from '@/components/common/MarkdownView.vue'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { usePagination } from '@/composables/usePagination'
import { useUserStore } from '@/stores/user'
import { message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { EditorialView, SolutionSummary } from '@/types'
import { useSolutionContext } from './useSolutionContext'

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()
const { problemId, problemBase, solutionsBase } = useSolutionContext()

const activeTab = ref<'official' | 'share'>('share')
const editorial = ref<EditorialView | null>(null)
const editorialLoading = ref(false)

const solutions = ref<SolutionSummary[]>([])
const loading = ref(false)
const keyword = ref('')
const mineOnly = ref(false)
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

async function loadEditorial(): Promise<void> {
  editorialLoading.value = true
  try {
    editorial.value = await getEditorial(problemId.value)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    editorialLoading.value = false
  }
}

async function loadSolutions(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await listSolutions(problemId.value, {
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      mine: mineOnly.value || undefined,
    })
    if (!isCurrent(seq)) return
    solutions.value = result.items
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
  void loadSolutions()
}

function onMineChange(value: boolean): void {
  mineOnly.value = value
  onSearch()
}

function onPageChange(value: number): void {
  changePage(value)
  void loadSolutions()
}

function write(): void {
  void router.push(`${solutionsBase.value}/new`)
}

const columns = computed<AppTableColumn<SolutionSummary>[]>(() => [
  {
    key: 'title',
    title: t('problems.solutions.titleLabel'),
    cell: (row) =>
      h('div', { class: 'min-w-0 py-0.5' }, [
        h('p', { class: 'truncate font-medium', title: row.title }, row.title),
        h(
          'p',
          { class: 'mt-0.5 line-clamp-2 text-[12px] text-muted-foreground' },
          row.excerpt || t('problems.solutions.noExcerpt'),
        ),
      ]),
  },
  {
    key: 'author',
    title: t('admin.solutions.author'),
    width: '140px',
    cell: (row) => row.author.nickname,
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
  {
    key: 'comment_count',
    title: t('admin.solutions.commentCount'),
    width: '100px',
    align: 'right',
    cell: (row) => String(row.comment_count),
    cellClass: 'tabular-nums text-muted-foreground',
  },
  {
    key: 'status',
    title: t('admin.solutions.status'),
    width: '100px',
    cell: (row) =>
      h(ToneBadge, {
        tone: row.status === 'published' ? 'success' : 'default',
        label:
          row.status === 'published'
            ? t('problems.solutions.status.published')
            : t('problems.solutions.status.removed'),
      }),
  },
  {
    key: 'updated_at',
    title: t('admin.solutions.updatedAt'),
    width: '160px',
    cell: (row) => formatDateTime(row.updated_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
])

onMounted(() => {
  void loadEditorial()
  void loadSolutions()
})
</script>

<template>
  <WorkbenchShell :title="t('problems.solutions.title')">
    <template #actions>
      <Button variant="outline" size="sm" @click="router.push(problemBase)">
        <ArrowLeft class="size-4" />
        {{ t('problems.solutions.backToProblem') }}
      </Button>
      <RefreshButton
        :loading="loading || editorialLoading"
        :label="t('action.refresh')"
        @click="
          () => {
            loadEditorial()
            loadSolutions()
          }
        "
      />
    </template>

    <Tabs v-model="activeTab" class="min-h-0 flex-1 gap-2">
      <TabsList class="shrink-0">
        <TabsTrigger value="official" class="px-3 text-[12.5px]">
          {{ t('problems.solutions.officialTab') }}
        </TabsTrigger>
        <TabsTrigger value="share" class="px-3 text-[12.5px]">
          {{ t('problems.solutions.shareTab') }}
        </TabsTrigger>
      </TabsList>

      <TabsContent value="official" class="min-h-0 overflow-y-auto">
        <div v-if="editorialLoading" class="grid h-40 place-items-center">
          <span class="text-[13px] text-muted-foreground">{{ t('common.loading') }}</span>
        </div>
        <div v-else class="rounded-xl border border-border bg-card px-5 py-4">
          <MarkdownView v-if="editorial?.solution" :source="editorial.solution" />
          <p v-else class="py-8 text-center text-[13px] text-muted-foreground">
            {{ t('problems.solutions.officialEmpty') }}
          </p>
          <p
            v-if="editorial?.can_manage"
            class="mt-4 border-t border-border pt-3 text-[12px] text-muted-foreground"
          >
            {{ t('problems.solutions.officialManageHint') }}
          </p>
        </div>
      </TabsContent>

      <TabsContent value="share" class="flex min-h-0 flex-col gap-3">
        <SearchFilterBar
          :keyword="keyword"
          :placeholder="t('problems.solutions.searchPlaceholder')"
          @update:keyword="keyword = $event"
          @search="onSearch"
          @reset="onSearch"
        >
          <template #actions>
            <FilterCheckbox
              v-if="userStore.isLoggedIn"
              id="solutions-mine"
              :model-value="mineOnly"
              :label="t('problems.solutions.mineOnly')"
              @update:model-value="onMineChange"
            />
            <Button v-if="userStore.isLoggedIn" size="toolbar" @click="write">
              <PenLine class="size-4" />
              {{ t('problems.solutions.write') }}
            </Button>
          </template>
        </SearchFilterBar>

        <PaginatedTable
          :columns="columns"
          :data="solutions"
          :loading="loading"
          :total="total"
          :page="page"
          :page-size="pageSize"
          :empty-text="t(mineOnly ? 'problems.solutions.mineEmpty' : 'problems.solutions.empty')"
          :row-click="(row) => router.push(`${solutionsBase}/${row.id}`)"
          @update:page="onPageChange"
        />
      </TabsContent>
    </Tabs>
  </WorkbenchShell>
</template>
