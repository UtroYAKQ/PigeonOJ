<script setup lang="ts">
/**
 * 全站提交面板（/admin/submissions）：跨题目 / 跨用户提交查看（admin 专用）。
 * 筛选：提交类型（练习 / 比赛 / 验题）/ 提交人（昵称模糊）/ 题号（短 ID 或完整 UUID 文本输入）/
 * 状态 / 语言；点击行进提交查看上下文评测详情；行内「查看题目」进提交查看上下文题目预览。
 */
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NButton, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import * as adminApi from '@/api/admin'
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
import type { AdminSubmission } from '@/types'

const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const list = ref<AdminSubmission[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage } = usePagination()

const query = reactive({
  keyword: '',
  submit_type: null as string | null,
  status: null as string | null,
  language: null as string | null,
  /** 题号筛选：题目短 ID（UUID 前 8 位）或完整 UUID，回车 / 查询时解析为 problem_id 精确过滤 */
  problemQuery: '',
  resolvedProblemId: null as string | null,
})

/** 短 ID（8 位十六进制）→ 在当前列表中反查完整 problem_id；否则视为完整 UUID */
function resolveProblemId(raw: string): string | null {
  const value = raw.trim()
  if (!value) return null
  if (/^[0-9a-fA-F]{8}$/.test(value)) {
    const hit = list.value.find((s) => s.problem_id.startsWith(value.toLowerCase()))
    return hit?.problem_id ?? null
  }
  return value
}

const statusOptions = [
  { value: 'accepted', labelKey: 'problems.status.accepted' },
  { value: 'wrong_answer', labelKey: 'problems.status.wrong_answer' },
  { value: 'compile_error', labelKey: 'problems.status.compile_error' },
].map((o) => ({ value: o.value, label: t(o.labelKey) }))

const submitTypeOptions = (
  [
    { value: 'practice', labelKey: 'problems.submissionsManage.typePractice' },
    { value: 'contest', labelKey: 'problems.submissionsManage.typeContest' },
    { value: 'verify', labelKey: 'problems.submissionsManage.typeVerify' },
  ] as const
).map((o) => ({ value: o.value, label: t(o.labelKey) }))

const languageOptionsFiltered = languageOptions.map((o) => ({ label: o.label, value: o.value }))

const submitTypeMeta: Record<string, { labelKey: string; type: NaiveTagType }> = {
  practice: { labelKey: 'problems.submissionsManage.typePractice', type: 'default' },
  contest: { labelKey: 'problems.submissionsManage.typeContest', type: 'info' },
  verify: { labelKey: 'problems.submissionsManage.typeVerify', type: 'warning' },
}

// ---- 题号筛选（文本输入框：题目短 ID 或完整 UUID） ----
async function load() {
  loading.value = true
  try {
    const result = await adminApi.adminListSubmissions({
      page: page.value,
      page_size: pageSize.value,
      submit_type: query.submit_type || undefined,
      status: query.status || undefined,
      language: query.language || undefined,
      keyword: query.keyword || undefined,
      problem_id: query.resolvedProblemId || undefined,
    })
    list.value = result.items
    total.value = result.total
    // 短 ID 在当前页反查成功后回填完整 UUID，翻页 / 筛选时保持精确过滤
    if (query.problemQuery && !query.resolvedProblemId) {
      query.resolvedProblemId = resolveProblemId(query.problemQuery)
      if (query.resolvedProblemId && query.resolvedProblemId !== query.problemQuery) {
        return load()
      }
      if (!query.resolvedProblemId) message.warning(t('admin.submissions.problemNotFound'))
    }
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    loading.value = false
  }
}

function onSearch() {
  query.resolvedProblemId = resolveProblemId(query.problemQuery)
  if (query.problemQuery && !query.resolvedProblemId) {
    message.warning(t('admin.submissions.problemNotFound'))
    return
  }
  resetPage()
  load()
}

function clearProblem() {
  query.problemQuery = ''
  query.resolvedProblemId = null
  onSearch()
}

function goDetail(row: AdminSubmission) {
  // 提交查看上下文评测详情（复用题目管理详情组件；返回与面包屑留在提交查看动线）
  router.push(`/admin/submissions/problems/${row.problem_id}/submissions/${row.id}`)
}

/** 行内「查看题目」：提交查看上下文只读预览（留在提交查看动线，不跳题目管理） */
function goProblem(row: AdminSubmission) {
  router.push(`/admin/submissions/problems/${row.problem_id}/preview`)
}

const columns = computed<DataTableColumns<AdminSubmission>>(() => [
  {
    title: t('admin.submissions.problemId'),
    key: 'problem_id',
    width: 110,
    render: (row) => h('code', null, `#${row.problem_id.slice(0, 8)}`),
  },
  {
    title: t('admin.submissions.problem'),
    key: 'problem',
    minWidth: 200,
    ellipsis: { tooltip: true },
    render: (row) => row.problem_title ?? '—',
  },
  {
    title: t('action.view'),
    key: 'actions',
    width: 100,
    render(row) {
      return h(
        NButton,
        {
          text: true,
          type: 'primary',
          onClick: (e: MouseEvent) => {
            e.stopPropagation()
            goProblem(row)
          },
        },
        { default: () => t('admin.submissions.viewProblem') },
      )
    },
  },
  {
    title: t('admin.submissions.submitter'),
    key: 'nickname',
    minWidth: 130,
    render: (row) => row.nickname,
  },
  {
    title: t('problems.detail.status'),
    key: 'status',
    minWidth: 140,
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
        {
          default: () => t(meta.labelKey),
        },
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

function rowProps(row: AdminSubmission) {
  return {
    style: 'cursor: pointer;',
    onClick: () => goDetail(row),
  }
}

onMounted(load)
</script>

<template>
  <WorkbenchShell>
    <template #header-extra>
      <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
    </template>

    <SearchFilterBar
      :keyword="query.keyword"
      :placeholder="t('admin.submissions.searchUser')"
      @update:keyword="
        (v: string) => {
          query.keyword = v
        }
      "
      @search="onSearch"
      @reset="onSearch"
    >
      <n-select
        v-model:value="query.submit_type"
        clearable
        style="width: 130px"
        :options="submitTypeOptions"
        :placeholder="t('problems.submissionsManage.allTypes')"
        @update:value="onSearch"
      />
      <n-select
        v-model:value="query.status"
        clearable
        style="width: 140px"
        :options="statusOptions"
        :placeholder="t('common.allStatus')"
        @update:value="onSearch"
      />
      <n-select
        v-model:value="query.language"
        clearable
        style="width: 150px"
        :options="languageOptionsFiltered"
        :placeholder="t('problems.submissionsManage.allLanguages')"
        @update:value="onSearch"
      />
      <n-input
        v-model:value="query.problemQuery"
        clearable
        style="width: 200px"
        :placeholder="t('admin.submissions.problemQuery')"
        @keyup.enter="onSearch"
        @clear="clearProblem"
      />
    </SearchFilterBar>

    <PaginatedDataTable
      :columns="columns"
      :data="list"
      :loading="loading"
      :total="total"
      v-model:page="page"
      v-model:page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      :empty-text="t('admin.submissions.empty')"
      :table-props="{ scrollX: 1160, rowProps }"
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

<style scoped></style>
