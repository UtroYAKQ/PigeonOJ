<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { listProblemSets } from '@/api/problemSets'
import FilterCheckbox from '@/components/common/FilterCheckbox.vue'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import ProblemSetVisibilityBadge from '@/components/problemsets/ProblemSetVisibilityBadge.vue'
import { usePagination } from '@/composables/usePagination'
import { useUserStore } from '@/stores/user'
import { message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { PageResult, ProblemSetSummary } from '@/types'

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const loading = ref(false)
const sets = ref<ProblemSetSummary[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()

const keyword = ref('')
/** 「我的」勾选仅对题单管理角色（admin/tutor）开放：只看本人未下线题单（含私有） */
const isManager = computed(() => userStore.isAdmin)
const mineOnly = ref(false)

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result: PageResult<ProblemSetSummary> = await listProblemSets({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      mine: mineOnly.value,
    })
    if (!isCurrent(seq)) return
    sets.value = result.items
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

onMounted(load)

const columns = computed<AppTableColumn<ProblemSetSummary>[]>(() => [
  {
    key: 'title',
    title: t('problemSets.list.titleLabel'),
    cell: (row) =>
      h('div', { class: 'flex flex-wrap items-center gap-2 py-0.5' }, [
        h('span', { class: 'font-medium text-[13.5px]' }, row.title),
        row.visibility === 'private'
          ? h(ToneBadge, { tone: 'danger', label: t('problemSets.list.privateTag') })
          : null,
      ]),
  },
  {
    key: 'visibility',
    title: t('problemSets.list.visibility'),
    width: '96px',
    cell: (row) => h(ProblemSetVisibilityBadge, { visibility: row.visibility }),
  },
  {
    key: 'item_count',
    title: t('problemSets.detail.problems'),
    width: '110px',
    align: 'right',
    cell: (row) => t('problemSets.list.itemCount', { count: row.item_count }),
    cellClass: 'tabular-nums text-muted-foreground',
  },
  {
    key: 'created_at',
    title: t('problemSets.list.createdAt'),
    width: '170px',
    cell: (row) => formatDateTime(row.created_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
])
</script>

<template>
  <!-- 题单中心（浏览）：管理入口统一在管理后台 /admin/problem-sets -->
  <WorkbenchShell :title="t('nav.problemSets')">
    <template #toolbar>
      <SearchFilterBar
        :keyword="keyword"
        :placeholder="t('problemSets.list.search')"
        search-width="300px"
        @update:keyword="keyword = $event"
        @search="onSearch"
        @reset="onSearch"
      >
        <template #actions>
          <FilterCheckbox
            v-if="isManager"
            id="problem-set-mine"
            :model-value="mineOnly"
            :label="t('problemSets.list.mineOnly')"
            @update:model-value="onMineChange"
          />
          <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
        </template>
      </SearchFilterBar>
    </template>

    <PaginatedTable
      :columns="columns"
      :data="sets"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      :empty-text="t('problemSets.list.empty')"
      :row-click="(row) => router.push(`/problem-sets/${row.id}`)"
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
        <span class="tabular-nums">{{ t('problemSets.list.totalCount', { count: total }) }}</span>
      </template>
    </PaginatedTable>
  </WorkbenchShell>
</template>
