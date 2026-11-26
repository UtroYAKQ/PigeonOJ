<script setup lang="ts">
/**
 * 题单管理（管理后台，admin/tutor）：全量题单列表（含私有 / 已下线）+ 新建；
 * 行整行点击进入题单详情（编辑信息 / 编排题目 / 下线均收敛在详情页）。
 */
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { adminListProblemSets } from '@/api/admin'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import ProblemSetVisibilityBadge from '@/components/problemsets/ProblemSetVisibilityBadge.vue'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { usePagination } from '@/composables/usePagination'
import { message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { PageResult, ProblemSetSummary } from '@/types'

const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const sets = ref<ProblemSetSummary[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()

const keyword = ref('')
const statusFilter = ref<'active' | 'archived' | null>(null)
/** 来源筛选：solo=全站题单 / team=团队题单（空 = 全部来源） */
const ownershipFilter = ref<'solo' | 'team' | null>(null)

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result: PageResult<ProblemSetSummary> = await adminListProblemSets({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      status: statusFilter.value ?? undefined,
      ownership: ownershipFilter.value ?? undefined,
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

onMounted(load)

const statusValue = computed(() => statusFilter.value ?? 'all')
const ownershipValue = computed(() => ownershipFilter.value ?? 'all')

function updateStatus(value: string): void {
  statusFilter.value = value === 'all' ? null : (value as 'active' | 'archived')
  onSearch()
}

function updateOwnership(value: string): void {
  ownershipFilter.value = value === 'all' ? null : (value as 'solo' | 'team')
  onSearch()
}

const columns = computed<AppTableColumn<ProblemSetSummary>[]>(() => [
  {
    key: 'title',
    title: t('problemSets.list.titleLabel'),
    cell: (row) =>
      h('div', { class: 'flex flex-wrap items-center gap-2 py-0.5' }, [
        h('span', { class: 'font-medium text-[13.5px]' }, row.title),
        row.team_id
          ? h(ToneBadge, { tone: 'primary', label: t('problemSets.list.ownershipTeam') })
          : null,
      ]),
  },
  {
    key: 'item_count',
    title: t('problemSets.detail.problems'),
    width: '90px',
    align: 'right',
    cell: (row) => t('problemSets.list.itemCount', { count: row.item_count }),
    cellClass: 'tabular-nums text-muted-foreground',
  },
  {
    key: 'visibility',
    title: t('problemSets.list.visibility'),
    width: '96px',
    cell: (row) => h(ProblemSetVisibilityBadge, { visibility: row.visibility }),
  },
  {
    key: 'status',
    title: t('problemSets.list.status'),
    width: '90px',
    cell: (row) =>
      h(ToneBadge, {
        tone: row.status === 'active' ? 'info' : 'warning',
        label: t(
          row.status === 'active' ? 'problemSets.list.active' : 'problemSets.detail.archived',
        ),
      }),
  },
  {
    key: 'created_at',
    title: t('problemSets.list.createdAt'),
    width: '170px',
    cell: (row) => formatDateTime(row.created_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
])

/** 新建走独立页面（表单含 Markdown 介绍）；编辑入口在题单详情页 */
function openCreate(): void {
  router.push('/admin/problem-sets/new')
}
</script>

<template>
  <WorkbenchShell :title="t('nav.problemSetsManage')">
    <template #toolbar>
      <SearchFilterBar
        :keyword="keyword"
        :placeholder="t('problemSets.list.search')"
        search-width="260px"
        @update:keyword="keyword = $event"
        @search="onSearch"
        @reset="onSearch"
      >
        <Select
          :model-value="statusValue"
          @update:model-value="(value) => updateStatus(String(value))"
        >
          <SelectTrigger
            class="h-9 w-[130px] text-[13px]"
            :aria-label="t('problemSets.list.status')"
          >
            <SelectValue :placeholder="t('common.allStatus')" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{{ t('common.allStatus') }}</SelectItem>
            <SelectItem value="active">{{ t('problemSets.list.active') }}</SelectItem>
            <SelectItem value="archived">{{ t('problemSets.detail.archived') }}</SelectItem>
          </SelectContent>
        </Select>

        <Select
          :model-value="ownershipValue"
          @update:model-value="(value) => updateOwnership(String(value))"
        >
          <SelectTrigger
            class="h-9 w-[130px] text-[13px]"
            :aria-label="t('problemSets.list.ownership')"
          >
            <SelectValue :placeholder="t('problemSets.list.ownershipAll')" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{{ t('problemSets.list.ownershipAll') }}</SelectItem>
            <SelectItem value="solo">{{ t('problemSets.list.ownershipSolo') }}</SelectItem>
            <SelectItem value="team">{{ t('problemSets.list.ownershipTeam') }}</SelectItem>
          </SelectContent>
        </Select>

        <template #actions>
          <Button size="toolbar" @click="openCreate">
            {{ t('problemSets.list.create') }}
          </Button>
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
      show-size-picker
      :empty-text="t('problemSets.list.empty')"
      :row-click="(row) => router.push(`/admin/problem-sets/${row.id}`)"
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
