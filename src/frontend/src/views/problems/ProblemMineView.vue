<script setup lang="ts">
import { CirclePlus, EditPen, TurnOff, View } from '@element-plus/icons-vue'
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NButton, NIcon, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import { archiveProblem, listProblems } from '@/api/problems'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import RefreshButton from '@/components/RefreshButton.vue'
import { problemStatusTagType, problemStatusLabelKey } from '@/constants/problemStatus'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import type { PageResult, ProblemSummary } from '@/types'

type ProblemStatus = 'draft' | 'published' | 'archived'

const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const list = ref<ProblemSummary[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage } = usePagination()
const query = reactive({
  keyword: '',
  status: '' as ProblemStatus | '',
})

async function load() {
  loading.value = true
  try {
    const result: PageResult<ProblemSummary> = await listProblems({
      page: page.value,
      page_size: pageSize.value,
      keyword: query.keyword || undefined,
      scope: 'mine',
      status: query.status || undefined,
    })
    list.value = result.items
    total.value = result.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.list.loadFailed'))
  } finally {
    loading.value = false
  }
}

function switchStatus(value: string) {
  query.status = value as ProblemStatus | ''
  resetPage()
  load()
}
function onSearch() {
  resetPage()
  load()
}
function goEdit(row: ProblemSummary) {
  router.push(`/admin/problems/${row.id}/edit/statement`)
}
function goDetail(row: ProblemSummary) {
  // 管理动线只读预览：留在后台，不进前台写题页
  router.push(`/admin/problems/${row.id}/preview`)
}

function doArchive(row: ProblemSummary) {
  confirmAsyncDialog({
    title: t('problems.detail.archive'),
    content: t('problems.mine.archiveConfirm'),
    positiveText: t('problems.detail.archive'),
    action: async () => {
      Object.assign(row, await archiveProblem(row.id))
    },
    successMessage: t('problems.detail.archiveSuccess'),
    onAfterSuccess: () => load(),
  })
}

onMounted(load)

const columns = computed<DataTableColumns<ProblemSummary>>(() => [
  {
    title: t('problems.list.name'),
    key: 'title',
    minWidth: 260,
    render(row) {
      const bits = [`#${(row.id || '').slice(0, 8)}`]
      if (row.visibility && row.visibility !== 'public')
        bits.push(t(`problems.visibility.${row.visibility}`))
      return h('div', { class: 'problem-name' }, [
        h('strong', null, row.title),
        h('span', null, bits.join(' · ')),
      ])
    },
  },
  {
    title: t('problems.list.type'),
    key: 'status',
    width: 100,
    render(row) {
      return h(
        NTag,
        { size: 'small', bordered: false, type: problemStatusTagType(row.status) },
        { default: () => t(problemStatusLabelKey[row.status] ?? row.status) },
      )
    },
  },
  {
    title: t('problems.manage.shareTitle'),
    key: 'is_verified',
    width: 110,
    render(row) {
      if (row.needs_reverification) {
        return h(
          NTag,
          { size: 'small', bordered: false, type: 'warning' },
          { default: () => t('problems.manage.reverifyTag') },
        )
      }
      return h(
        NTag,
        { size: 'small', bordered: false, type: row.is_verified ? 'success' : 'default' },
        {
          default: () =>
            row.is_verified
              ? t('problems.manage.verifiedTag')
              : t('problems.manage.unverifiedTag'),
        },
      )
    },
  },
  {
    title: t('problems.list.limits'),
    key: 'limits',
    width: 180,
    render: (row) => `${row.time_limit_ms} ms / ${row.memory_limit_mb} MB`,
  },
  {
    title: t('action.edit'),
    key: 'actions',
    width: 210,
    fixed: 'right',
    render(row) {
      const buttons: ReturnType<typeof h>[] = []
      // 行内操作：text 按钮 + 语义图标（docs/frontend.md 按钮规范）；归档为唯一危险操作。
      // 点击必须 stopPropagation，否则冒泡到行 onClick 会把路由覆盖成行的目标（如预览页）
      function actionButton(icon: typeof View, label: string, onClick: () => void, type?: 'primary' | 'error') {
        return h(
          NButton,
          {
            text: true,
            type,
            class: 'cell-actions__btn',
            onClick: (event: MouseEvent) => {
              event.stopPropagation()
              onClick()
            },
          },
          {
            icon: () => h(NIcon, { size: 14 }, { default: () => h(icon) }),
            default: () => label,
          },
        )
      }
      if (row.status === 'draft') {
        buttons.push(
          actionButton(View, t('action.view'), () => goDetail(row)),
          actionButton(EditPen, t('action.edit'), () => goEdit(row), 'primary'),
        )
      } else if (row.status === 'published') {
        buttons.push(
          actionButton(View, t('action.view'), () => goDetail(row)),
          actionButton(EditPen, t('action.edit'), () => goEdit(row), 'primary'),
          actionButton(TurnOff, t('problems.detail.archive'), () => doArchive(row), 'error'),
        )
      } else {
        buttons.push(
          actionButton(View, t('action.view'), () => goDetail(row)),
        )
      }
      return h('div', { class: 'cell-actions' }, buttons)
    },
  },
])

function rowProps(row: ProblemSummary) {
  // 归档题只读：行点击不跳转（避免被带出管理后台），查看走操作列「详情」
  if (row.status === 'archived') return { style: 'cursor: default;' }
  const target =
    row.status === 'draft' ? `/admin/problems/${row.id}/edit/statement` : `/admin/problems/${row.id}/preview`
  return {
    style: 'cursor: pointer;',
    onClick: () => router.push(target),
  }
}
</script>

<template>
  <WorkbenchShell>
      <SearchFilterBar
        :keyword="query.keyword"
        :placeholder="t('problems.mine.search')"
        search-width="280px"
        @update:keyword="(v: string) => { query.keyword = v }"
        @search="onSearch"
        @reset="onSearch"
      >
        <template #actions>
          <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
          <n-button type="primary" @click="router.push('/admin/problems/new')">
            <template #icon>
              <n-icon :component="CirclePlus" />
            </template>
            {{ t('problems.list.create') }}
          </n-button>
        </template>
      </SearchFilterBar>

      <n-tabs type="line" size="small" class="status-tabs" :value="query.status || 'all'" @update:value="switchStatus">
        <n-tab-pane name="all" :tab="t('problems.mine.all')" />
        <n-tab-pane name="draft" :tab="t('problems.list.statusDraft')" />
        <n-tab-pane name="published" :tab="t('problems.list.statusPublished')" />
        <n-tab-pane name="archived" :tab="t('problems.list.statusArchived')" />
      </n-tabs>

      <PaginatedDataTable
        :columns="columns"
        :data="list"
        :loading="loading"
        :total="total"
        v-model:page="page"
        v-model:page-size="pageSize"
        :page-sizes="[20, 50, 100]"
        :empty-text="t('problems.mine.empty')"
        :table-props="{ scrollX: 980, rowProps }"
        @update:page="(p: number) => { changePage(p); load() }"
        @update:page-size="(s: number) => { changeSize(s); load() }"
      >
        <template #pager-left>
          <span class="pager__total">{{ t('problems.list.totalCount', { count: total }) }}</span>
        </template>
      </PaginatedDataTable>
  </WorkbenchShell>
</template>

<style scoped>
.status-tabs {
  margin-bottom: 4px;
}
.problem-name {
  display: grid;
  gap: 4px;
}
.problem-name strong {
  font-size: 14px;
}
.problem-name span {
  color: var(--app-text-secondary);
  font-size: 12px;
}
/* 行内操作按钮增强：中等字重 + 悬停浅底，弥补 text 形态的弱可点感 */
.table-fill :deep(.cell-actions__btn) {
  font-weight: 500;
  padding: 2px 4px;
  border-radius: 4px;
  transition: background-color 0.15s ease;
}
.table-fill :deep(.cell-actions__btn:hover) {
  background: var(--app-muted-bg);
}
@media (max-width: 700px) {
  .pager {
    justify-content: center;
  }
}
</style>
