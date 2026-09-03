<script setup lang="ts">
/**
 * 题目管理 · 提交列表（上下文路由 /admin/problems/:id/submissions）：
 * 面向题目管理角色（创建者 / admin / tutor）查看该题全员提交，
 * 经题目上下文端点读取（后端按 can_manage_problem 校验），不跳出管理动线。
 * 支持昵称关键字 / 语言 / 状态筛选；点击行进入评测详情（上下文路由内跳转）。
 */
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import { getProblem, listProblemSubmissions } from '@/api/problems'
import { message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import RefreshButton from '@/components/RefreshButton.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import StatusTag from '@/components/StatusTag.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { formatDateTime } from '@/utils/format'
import { languageOptions } from '@/constants/languages'
import type { NaiveTagType } from '@/constants/dict'
import type { ProblemDetail, ProblemSubmissionItem } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const problemId = String(route.params.id)
const problem = ref<ProblemDetail | null>(null)
const loading = ref(false)
const list = ref<ProblemSubmissionItem[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage } = usePagination()
/** n-select 筛选以 null 表示不限：'' 会被 naive-ui fallback 渲染成空串，placeholder 不展示 */
const query = reactive({
  status: '',
  keyword: '',
  language: null as string | null,
  submit_type: null as string | null,
})

/** 状态筛选页签（全部 + 常用结果；标签复用 problems.status 字典） */
const statusTabs = [
  { value: '', labelKey: 'problems.mine.all' },
  { value: 'accepted', labelKey: 'problems.status.accepted' },
  { value: 'wrong_answer', labelKey: 'problems.status.wrong_answer' },
  { value: 'compile_error', labelKey: 'problems.status.compile_error' },
] as const

/** 语言筛选选项（复用判题语言字典；空值「全部语言」由 clearable placeholder 承担） */
const languageFilterOptions = languageOptions.map((option) => ({
  label: option.label,
  value: option.value,
}))

/** 提交类型筛选选项（练习 / 比赛 / 验题；空值「全部类型」由 clearable placeholder 承担） */
const submitTypeFilterOptions = (
  [
    { value: 'practice', labelKey: 'problems.submissionsManage.typePractice' },
    { value: 'contest', labelKey: 'problems.submissionsManage.typeContest' },
    { value: 'verify', labelKey: 'problems.submissionsManage.typeVerify' },
  ] as const
).map((option) => ({ value: option.value, label: t(option.labelKey) }))

/** 提交类型 → 标签（练习 / 比赛 / 验题） */
const submitTypeMeta: Record<string, { labelKey: string; type: NaiveTagType }> = {
  practice: { labelKey: 'problems.submissionsManage.typePractice', type: 'default' },
  contest: { labelKey: 'problems.submissionsManage.typeContest', type: 'info' },
  verify: { labelKey: 'problems.submissionsManage.typeVerify', type: 'warning' },
}

async function loadProblem() {
  try {
    problem.value = await getProblem(problemId)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
  }
}

async function load() {
  loading.value = true
  try {
    const result = await listProblemSubmissions(problemId, {
      page: page.value,
      page_size: pageSize.value,
      status: query.status || undefined,
      keyword: query.keyword || undefined,
      language: query.language || undefined,
      submit_type: query.submit_type || undefined,
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

function switchStatus(value: string) {
  query.status = value
  resetPage()
  load()
}

function onSearch() {
  resetPage()
  load()
}

function goDetail(row: ProblemSubmissionItem) {
  router.push(`/admin/problems/${problemId}/submissions/${row.id}`)
}

const pageTitle = computed(() => problem.value?.title ?? t('problems.submissionsManage.title'))

const columns = computed<DataTableColumns<ProblemSubmissionItem>>(() => [
  {
    title: t('problems.submissionsManage.user'),
    key: 'nickname',
    minWidth: 140,
    render(row) {
      return h('div', { class: 'submitter' }, [
        h('strong', null, row.nickname),
        h('span', null, `#${row.user_id.slice(0, 8)}`),
      ])
    },
  },
  {
    title: t('problems.detail.status'),
    key: 'status',
    minWidth: 150,
    render: (row) => h(StatusTag, { status: row.status }),
  },
  {
    title: t('problems.submission.score'),
    key: 'score',
    width: 80,
    render: (row) => row.score ?? '-',
  },
  {
    title: t('problems.submission.time'),
    key: 'time',
    width: 100,
    render: (row) => `${row.time_used_ms ?? '-'} ms`,
  },
  {
    title: t('problems.submission.memory'),
    key: 'memory',
    width: 110,
    render: (row) => `${row.memory_used_kb ?? '-'} KB`,
  },
  { title: t('problems.detail.language'), key: 'language', width: 110 },
  {
    title: t('problems.submissionsManage.type'),
    key: 'submit_type',
    width: 90,
    render(row) {
      const meta = submitTypeMeta[row.submit_type]
      if (!meta) return row.submit_type
      return h(
        NTag,
        { size: 'small', bordered: false, type: meta.type },
        { default: () => t(meta.labelKey) },
      )
    },
  },
  {
    title: t('problems.submissionsManage.submitTime'),
    key: 'created_at',
    width: 170,
    render: (row) => formatDateTime(row.created_at),
  },
])

/** 点击行进入该提交的评测详情（上下文路由内跳转） */
function rowProps(row: ProblemSubmissionItem) {
  return {
    style: 'cursor: pointer;',
    onClick: () => goDetail(row),
  }
}

onMounted(() => {
  loadProblem()
  load()
})
</script>

<template>
  <WorkbenchShell>
    <template #header>
      <div class="submissions-head">
        <strong class="submissions-head__title">{{ pageTitle }}</strong>
        <span class="submissions-head__sub">{{ t('problems.submissionsManage.title') }}</span>
      </div>
    </template>

    <SearchFilterBar
      :keyword="query.keyword"
      :placeholder="t('problems.submissionsManage.search')"
      @update:keyword="
        (v: string) => {
          query.keyword = v
        }
      "
      @search="onSearch"
      @reset="onSearch"
    >
      <n-select
        v-model:value="query.language"
        clearable
        style="width: 160px"
        :options="languageFilterOptions"
        :placeholder="t('problems.submissionsManage.allLanguages')"
        @update:value="onSearch"
      />
      <n-select
        v-model:value="query.submit_type"
        clearable
        style="width: 130px"
        :options="submitTypeFilterOptions"
        :placeholder="t('problems.submissionsManage.allTypes')"
        @update:value="onSearch"
      />
      <template #actions>
        <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
      </template>
    </SearchFilterBar>

    <n-tabs
      type="line"
      size="small"
      class="status-tabs"
      :value="query.status || 'all'"
      @update:value="switchStatus"
    >
      <n-tab-pane
        v-for="tab in statusTabs"
        :key="tab.value"
        :name="tab.value || 'all'"
        :tab="t(tab.labelKey)"
      />
    </n-tabs>

    <PaginatedDataTable
      :columns="columns"
      :data="list"
      :loading="loading"
      :total="total"
      v-model:page="page"
      v-model:page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      :empty-text="t('problems.submissionsManage.empty')"
      :table-props="{ scrollX: 950, rowProps }"
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
        <span class="pager__total">
          {{ t('problems.submissionsManage.totalCount', { count: total }) }}
        </span>
      </template>
    </PaginatedDataTable>
  </WorkbenchShell>
</template>

<style scoped>
.status-tabs {
  margin-bottom: 4px;
}
.submissions-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}
.submissions-head__title {
  font-size: 16px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.submissions-head__sub {
  flex-shrink: 0;
  color: var(--app-text-secondary);
  font-size: 12px;
}
.submitter {
  display: grid;
  gap: 2px;
}
.submitter strong {
  font-size: 14px;
}
.submitter span {
  color: var(--app-text-secondary);
  font-size: 12px;
}
@media (max-width: 700px) {
  .pager {
    justify-content: center;
  }
}
</style>
