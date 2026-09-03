<script setup lang="ts">
/**
 * 题单管理（管理后台，admin/tutor；docs/contracts/problem-sets.md）：
 * 全量题单列表（含私有 / 已下线）+ 新建；行整行点击进入题单详情
 * （编辑信息 / 编排题目 / 下线均收敛在详情页）。
 */
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import RefreshButton from '@/components/RefreshButton.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import ProblemSetEditModal from '@/components/problemsets/ProblemSetEditModal.vue'
import { adminListProblemSets } from '@/api/admin'
import { message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
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

async function load() {
  const seq = beginLoad()
  loading.value = true
  try {
    const result: PageResult<ProblemSetSummary> = await adminListProblemSets({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      status: statusFilter.value ?? undefined,
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

function onSearch() {
  resetPage()
  load()
}

function changeStatus() {
  resetPage()
  load()
}

onMounted(load)

const statusOptions = computed(() => [
  { label: t('common.allStatus'), value: 'all' },
  { label: t('problemSets.list.active'), value: 'active' },
  { label: t('problemSets.detail.archived'), value: 'archived' },
])
const statusValue = computed({
  get: () => statusFilter.value ?? 'all',
  set: (v: string) => {
    statusFilter.value = v === 'all' ? null : (v as 'active' | 'archived')
    changeStatus()
  },
})

const columns = computed<DataTableColumns<ProblemSetSummary>>(() => [
  {
    title: t('problemSets.list.titleLabel'),
    key: 'title',
    minWidth: 240,
    render(row) {
      return h('div', { class: 'set-name' }, [
        h('strong', null, row.title),
        row.description ? h('span', null, row.description) : null,
      ])
    },
  },
  {
    title: t('problemSets.detail.problems'),
    key: 'item_count',
    width: 90,
    render: (row) => t('problemSets.list.itemCount', { count: row.item_count }),
  },
  {
    title: t('problemSets.list.visibility'),
    key: 'visibility',
    width: 90,
    render: (row) =>
      h(
        NTag,
        {
          size: 'small',
          bordered: false,
          type: row.visibility === 'public' ? 'success' : 'default',
        },
        {
          default: () =>
            t(
              row.visibility === 'public'
                ? 'problemSets.list.visibilityPublic'
                : 'problemSets.list.visibilityPrivate',
            ),
        },
      ),
  },
  {
    title: t('problemSets.list.status'),
    key: 'status',
    width: 90,
    render: (row) =>
      h(
        NTag,
        { size: 'small', bordered: false, type: row.status === 'active' ? 'info' : 'warning' },
        {
          default: () =>
            t(row.status === 'active' ? 'problemSets.list.active' : 'problemSets.detail.archived'),
        },
      ),
  },
  {
    title: t('problemSets.list.createdAt'),
    key: 'created_at',
    width: 160,
    render: (row) => formatDateTime(row.created_at),
  },
])

/** 新建 / 编辑 / 下线入口收敛在题单详情页，列表行整行点击进入详情 */
function rowProps(row: ProblemSetSummary) {
  return {
    style: 'cursor: pointer;',
    onClick: () => router.push(`/admin/problem-sets/${row.id}`),
  }
}

/** 新建题单弹窗（problemSet=null 表示新建） */
const editorShow = ref(false)
function openCreate() {
  editorShow.value = true
}
</script>

<template>
  <WorkbenchShell>
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('problemSets.list.search')"
      search-width="260px"
      manual
      @update:keyword="
        (v: string) => {
          keyword = v
        }
      "
      @search="onSearch"
      @reset="onSearch"
    >
      <n-select
        v-model:value="statusValue"
        style="width: 130px"
        :options="statusOptions"
        :aria-label="t('problemSets.list.status')"
      />
      <template #actions>
        <n-button type="primary" size="small" @click="openCreate">
          {{ t('problemSets.list.create') }}
        </n-button>
        <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
      </template>
    </SearchFilterBar>

    <PaginatedDataTable
      :columns="columns"
      :data="sets"
      :loading="loading"
      :total="total"
      v-model:page="page"
      v-model:page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      :empty-text="t('problemSets.list.empty')"
      :table-props="{ rowProps }"
      @update:page="
        (p: number) => {
          changePage(p)
          load()
        }
      "
      @update:page-size="
        (s: number) => {
          changeSize(s)
          load()
        }
      "
    >
      <template #pager-left>
        <span class="pager__total">{{ t('problemSets.list.totalCount', { count: total }) }}</span>
      </template>
    </PaginatedDataTable>

    <ProblemSetEditModal v-model:show="editorShow" :problem-set="null" @saved="load" />
  </WorkbenchShell>
</template>

<style scoped>
.set-name {
  display: grid;
  gap: 4px;
}
.set-name strong {
  font-size: 14px;
}
.set-name span {
  color: var(--app-text-secondary);
  font-size: 12px;
}
</style>
