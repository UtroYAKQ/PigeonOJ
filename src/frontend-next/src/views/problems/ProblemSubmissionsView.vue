<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { getProblem, listProblemSubmissions } from '@/api/problems'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { languageOptions } from '@/constants/languages'
import { usePagination } from '@/composables/usePagination'
import { formatDateTime } from '@/utils/format'
import { message } from '@/utils/feedback'
import type { ProblemDetail, ProblemSubmissionItem } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const problemId = String(route.params.id)
const problem = ref<ProblemDetail | null>(null)
const loading = ref(false)
const list = ref<ProblemSubmissionItem[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage } = usePagination()

const query = reactive({ status: 'all', keyword: '', language: 'all', submitType: 'all' })

const statusTabs = [
  { value: 'all', labelKey: 'problems.mine.all' },
  { value: 'accepted', labelKey: 'problems.status.accepted' },
  { value: 'wrong_answer', labelKey: 'problems.status.wrong_answer' },
  { value: 'compile_error', labelKey: 'problems.status.compile_error' },
] as const

const submitTypes = [
  { value: 'practice', labelKey: 'problems.submissionsManage.typePractice', tone: 'primary' },
  { value: 'contest', labelKey: 'problems.submissionsManage.typeContest', tone: 'info' },
  { value: 'verify', labelKey: 'problems.submissionsManage.typeVerify', tone: 'warning' },
] as const

async function loadProblem(): Promise<void> {
  try {
    problem.value = await getProblem(problemId)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
  }
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const result = await listProblemSubmissions(problemId, {
      page: page.value,
      page_size: pageSize.value,
      status: query.status === 'all' ? undefined : (query.status as never),
      keyword: query.keyword || undefined,
      language: query.language === 'all' ? undefined : query.language,
      submit_type: query.submitType === 'all' ? undefined : query.submitType,
    })
    list.value = result.items
    total.value = result.total
  } catch (error) {
    message.error(
      error instanceof Error ? error.message : t('problems.submissionsManage.loadFailed'),
    )
  } finally {
    loading.value = false
  }
}

function onSearch(): void {
  resetPage()
  void load()
}

function goDetail(row: ProblemSubmissionItem): void {
  router.push(`/admin/problems/${problemId}/submissions/${row.id}`)
}

const pageTitle = computed(() => problem.value?.title ?? t('problems.submissionsManage.title'))

const columns = computed<AppTableColumn<ProblemSubmissionItem>[]>(() => [
  {
    key: 'nickname',
    title: t('problems.submissionsManage.user'),
    width: '160px',
    cell: (row) =>
      h('div', {}, [
        h('div', { class: 'font-medium text-[13px]' }, row.nickname),
        h(
          'div',
          { class: 'font-mono text-[11px] text-muted-foreground' },
          `#${row.user_id.slice(0, 8)}`,
        ),
      ]),
  },
  {
    key: 'status',
    title: t('problems.detail.status'),
    width: '140px',
    cell: (row) => h(StatusTag, { status: row.status }),
  },
  {
    key: 'score',
    title: t('problems.submission.score'),
    width: '72px',
    align: 'right',
    cell: (row) => row.score ?? '-',
    cellClass: 'tabular-nums',
  },
  {
    key: 'time',
    title: t('problems.submission.time'),
    width: '100px',
    align: 'right',
    cell: (row) => `${row.time_used_ms ?? '-'} ms`,
    cellClass: 'tabular-nums text-muted-foreground',
  },
  {
    key: 'memory',
    title: t('problems.submission.memory'),
    width: '100px',
    align: 'right',
    cell: (row) => `${row.memory_used_kb ?? '-'} KB`,
    cellClass: 'tabular-nums text-muted-foreground',
  },
  { key: 'language', title: t('problems.detail.language'), width: '110px' },
  {
    key: 'submit_type',
    title: t('problems.submissionsManage.type'),
    width: '90px',
    cell: (row) => {
      const meta = submitTypes.find((item) => item.value === row.submit_type)
      return meta ? h(ToneBadge, { tone: meta.tone, label: t(meta.labelKey) }) : row.submit_type
    },
  },
  {
    key: 'created_at',
    title: t('problems.submissionsManage.submitTime'),
    width: '170px',
    cell: (row) => formatDateTime(row.created_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
])

onMounted(() => {
  void loadProblem()
  void load()
})
</script>

<template>
  <WorkbenchShell>
    <template #title>
      <div class="flex min-w-0 items-baseline gap-2">
        <h1 class="truncate text-xl font-semibold leading-tight tracking-tight">{{ pageTitle }}</h1>
        <span class="shrink-0 text-[12px] text-muted-foreground">
          {{ t('problems.submissionsManage.title') }}
        </span>
      </div>
    </template>

    <template #toolbar>
      <div class="space-y-2.5">
        <SearchFilterBar
          :keyword="query.keyword"
          :placeholder="t('problems.submissionsManage.search')"
          @update:keyword="query.keyword = $event"
          @search="onSearch"
          @reset="onSearch"
        >
          <Select v-model="query.language" @update:model-value="onSearch">
            <SelectTrigger class="h-9 w-[160px] text-[13px]">
              <SelectValue :placeholder="t('problems.submissionsManage.allLanguages')" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{{
                t('problems.submissionsManage.allLanguages')
              }}</SelectItem>
              <SelectItem v-for="item in languageOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </SelectItem>
            </SelectContent>
          </Select>
          <Select v-model="query.submitType" @update:model-value="onSearch">
            <SelectTrigger class="h-9 w-[134px] text-[13px]">
              <SelectValue :placeholder="t('problems.submissionsManage.allTypes')" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{{ t('problems.submissionsManage.allTypes') }}</SelectItem>
              <SelectItem v-for="item in submitTypes" :key="item.value" :value="item.value">
                {{ t(item.labelKey) }}
              </SelectItem>
            </SelectContent>
          </Select>
          <template #actions>
            <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
          </template>
        </SearchFilterBar>

        <Tabs
          :model-value="query.status"
          @update:model-value="
            (value) => {
              query.status = String(value)
              onSearch()
            }
          "
        >
          <TabsList>
            <TabsTrigger
              v-for="tab in statusTabs"
              :key="tab.value"
              :value="tab.value"
              class="px-3 text-[12px]"
            >
              {{ t(tab.labelKey) }}
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
    </template>

    <PaginatedTable
      :columns="columns"
      :data="list"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      show-size-picker
      :empty-text="t('problems.submissionsManage.empty')"
      :row-click="goDetail"
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
        <span class="tabular-nums">
          {{ t('problems.submissionsManage.totalCount', { count: total }) }}
        </span>
      </template>
    </PaginatedTable>
  </WorkbenchShell>
</template>
