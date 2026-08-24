<script setup lang="ts">
import { CirclePlus, Refresh, Search as SearchIcon } from '@element-plus/icons-vue'
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NButton, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import { archiveProblem, listProblems } from '@/api/problems'
import { dialog, message } from '@/utils/feedback'
import type {
  PageResult,
  ProblemDifficulty,
  ProblemSummary,
} from '@/types'

type ProblemStatus = 'draft' | 'published' | 'archived'

const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const list = ref<ProblemSummary[]>([])
const total = ref(0)
const query = reactive({
  page: 1,
  page_size: 20,
  keyword: '',
  difficulty: null as ProblemDifficulty | null,
  status: '' as ProblemStatus | '',
})

async function load() {
  loading.value = true
  try {
    const result: PageResult<ProblemSummary> = await listProblems({
      page: query.page,
      page_size: query.page_size,
      keyword: query.keyword || undefined,
      difficulty: query.difficulty || undefined,
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
  query.page = 1
  load()
}
function onSearch() {
  query.page = 1
  load()
}
function changeDifficulty() {
  query.page = 1
  load()
}
function changePage(page: number) {
  query.page = page
  load()
}
function changeSize(size: number) {
  query.page_size = size
  query.page = 1
  load()
}
function goEdit(row: ProblemSummary) {
  router.push(`/admin/problems/${row.id}/edit`)
}
function goDetail(row: ProblemSummary) {
  router.push(`/problems/${row.id}`)
}

function doArchive(row: ProblemSummary) {
  dialog.warning({
    title: t('problems.detail.archive'),
    content: t('problems.mine.archiveConfirm'),
    positiveText: t('problems.detail.archive'),
    negativeText: t('action.cancel'),
    onPositiveClick: async () => {
      try {
        Object.assign(row, await archiveProblem(row.id))
        message.success(t('problems.detail.archiveSuccess'))
        await load()
      } catch (error) {
        message.error(error instanceof Error ? error.message : t('common.operationFailed'))
      }
    },
  })
}

onMounted(load)

const difficultyOptions = computed(() => [
  { label: t('problems.difficulty.easy'), value: 'easy' },
  { label: t('problems.difficulty.medium'), value: 'medium' },
  { label: t('problems.difficulty.hard'), value: 'hard' },
])

const statusLabelKey: Record<string, string> = {
  draft: 'problems.list.statusDraft',
  published: 'problems.list.statusPublished',
  archived: 'problems.list.statusArchived',
}
function statusTagType(status: string): 'warning' | 'success' | 'default' {
  return status === 'draft' ? 'warning' : status === 'published' ? 'success' : 'default'
}
function difficultyTagType(value: ProblemDifficulty): 'error' | 'warning' | 'success' {
  return value === 'hard' ? 'error' : value === 'medium' ? 'warning' : 'success'
}

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
        { size: 'small', bordered: false, type: statusTagType(row.status) },
        { default: () => t(statusLabelKey[row.status] ?? row.status) },
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
    title: t('problems.list.difficulty'),
    key: 'difficulty',
    width: 100,
    render(row) {
      return h(
        NTag,
        { size: 'small', bordered: false, type: difficultyTagType(row.difficulty) },
        { default: () => t(`problems.difficulty.${row.difficulty}`) },
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
      if (row.status === 'draft') {
        buttons.push(
          h(
            NButton,
            { text: true, type: 'primary', onClick: () => goEdit(row) },
            { default: () => t('action.edit') },
          ),
        )
      } else if (row.status === 'published') {
        buttons.push(
          h(
            NButton,
            { text: true, onClick: () => goDetail(row) },
            { default: () => t('problems.detail.title') },
          ),
          h(
            NButton,
            { text: true, onClick: () => goEdit(row) },
            { default: () => t('action.edit') },
          ),
          h(
            NButton,
            { text: true, type: 'error', onClick: () => doArchive(row) },
            { default: () => t('problems.detail.archive') },
          ),
        )
      } else {
        buttons.push(
          h(
            NButton,
            { text: true, onClick: () => goDetail(row) },
            { default: () => t('problems.submission.back') },
          ),
        )
      }
      return h('div', { class: 'cell-actions' }, buttons)
    },
  },
])

function rowProps(row: ProblemSummary) {
  const target =
    row.status === 'draft' ? `/admin/problems/${row.id}/edit` : `/problems/${row.id}`
  return {
    style: 'cursor: pointer;',
    onClick: () => router.push(target),
  }
}
</script>

<template>
  <div class="page-fill">
    <n-card :bordered="false">
      <div class="toolbar">
        <n-input
          v-model:value="query.keyword"
          clearable
          class="toolbar__search"
          :placeholder="t('problems.mine.search')"
          @keyup.enter="onSearch"
          @clear="onSearch"
        >
          <template #prefix>
            <n-icon size="15"><SearchIcon /></n-icon>
          </template>
        </n-input>
        <n-select
          v-model:value="query.difficulty"
          class="toolbar__difficulty"
          clearable
          :options="difficultyOptions"
          :placeholder="t('problems.list.difficulty')"
          @update:value="changeDifficulty"
        />
        <n-button quaternary circle :loading="loading" :aria-label="t('action.refresh')" @click="load">
          <n-icon :component="Refresh" />
        </n-button>
        <div class="toolbar__actions">
          <n-button type="primary" @click="router.push('/admin/problems/new')">
            <template #icon>
              <n-icon :component="CirclePlus" />
            </template>
            {{ t('problems.list.create') }}
          </n-button>
        </div>
      </div>

      <n-tabs type="line" size="small" class="status-tabs" :value="query.status || 'all'" @update:value="switchStatus">
        <n-tab-pane name="all" :tab="t('problems.mine.all')" />
        <n-tab-pane name="draft" :tab="t('problems.list.statusDraft')" />
        <n-tab-pane name="published" :tab="t('problems.list.statusPublished')" />
        <n-tab-pane name="archived" :tab="t('problems.list.statusArchived')" />
      </n-tabs>

      <n-data-table
        v-if="loading || list.length"
        class="table-fill"
        :columns="columns"
        :data="list"
        :loading="loading"
        :scroll-x="980"
        :bordered="false"
        :bottom-bordered="false"
        :row-props="rowProps"
      />
      <div v-else class="table-fill-empty">
        <n-empty size="large" :description="t('problems.mine.empty')" />
      </div>

      <div class="pager">
        <span class="pager__total">{{ t('problems.list.totalCount', { count: total }) }}</span>
        <n-pagination
          :page="query.page"
          :page-size="query.page_size"
          :item-count="total"
          :page-sizes="[20, 50, 100]"
          show-size-picker
          @update:page="changePage"
          @update:page-size="changeSize"
        />
      </div>
    </n-card>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.toolbar__search {
  width: 280px;
}
.toolbar__difficulty {
  width: 150px;
}
.toolbar__actions {
  margin-left: auto;
  display: flex;
  gap: 10px;
}
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
.cell-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.pager {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--app-border);
}
.pager__total {
  color: var(--app-text-secondary);
  font-size: 13px;
}
@media (max-width: 700px) {
  .toolbar__search,
  .toolbar__difficulty {
    width: 100%;
  }
  .pager {
    justify-content: center;
  }
}
</style>
