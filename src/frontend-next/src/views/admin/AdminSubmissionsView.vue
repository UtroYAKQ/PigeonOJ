<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { X } from '@lucide/vue'

import { adminListSubmissions } from '@/api/admin'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { languageOptions } from '@/constants/languages'
import type { TagType } from '@/constants/dict'
import { usePagination } from '@/composables/usePagination'
import { message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { AdminSubmission } from '@/types'

const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const list = ref<AdminSubmission[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()

const query = reactive({
  keyword: '',
  submitType: 'all',
  status: 'all',
  language: 'all',
  /** 题号筛选：题目短 ID（UUID 前 8 位）或完整 UUID，按回车 / 查询时解析为 problem_id 精确过滤 */
  problemQuery: '',
  resolvedProblemId: null as string | null,
})

const statusOptions = computed(() => [
  { value: 'accepted', label: t('problems.status.accepted') },
  { value: 'wrong_answer', label: t('problems.status.wrong_answer') },
  { value: 'compile_error', label: t('problems.status.compile_error') },
])

const submitTypes = [
  { value: 'practice', labelKey: 'problems.submissionsManage.typePractice' },
  { value: 'contest', labelKey: 'problems.submissionsManage.typeContest' },
  { value: 'verify', labelKey: 'problems.submissionsManage.typeVerify' },
] as const

const submitTypeMeta: Record<string, { labelKey: string; tone: TagType }> = {
  practice: { labelKey: 'problems.submissionsManage.typePractice', tone: 'primary' },
  contest: { labelKey: 'problems.submissionsManage.typeContest', tone: 'info' },
  verify: { labelKey: 'problems.submissionsManage.typeVerify', tone: 'warning' },
}

/** 短 ID（8 位十六进制）→ 在当前列表中反查完整 problem_id；否则视为完整 UUID */
function resolveProblemId(raw: string): string | null {
  const value = raw.trim()
  if (!value) return null
  if (/^[0-9a-fA-F]{8}$/.test(value)) {
    const hit = list.value.find((item) => item.problem_id.startsWith(value.toLowerCase()))
    return hit?.problem_id ?? null
  }
  return value
}

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await adminListSubmissions({
      page: page.value,
      page_size: pageSize.value,
      submit_type: query.submitType === 'all' ? undefined : query.submitType,
      status: query.status === 'all' ? undefined : query.status,
      language: query.language === 'all' ? undefined : query.language,
      keyword: query.keyword || undefined,
      problem_id: query.resolvedProblemId || undefined,
    })
    if (!isCurrent(seq)) return
    list.value = result.items
    total.value = result.total
    // 短 ID 在当前页反查成功后回填完整 UUID，翻页 / 筛选时保持精确过滤
    if (query.problemQuery && !query.resolvedProblemId) {
      const resolved = resolveProblemId(query.problemQuery)
      query.resolvedProblemId = resolved
      if (resolved && resolved !== query.problemQuery) {
        void load()
        return
      }
      if (!resolved) message.warning(t('admin.submissions.problemNotFound'))
    }
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

function onSearch(): void {
  query.resolvedProblemId = resolveProblemId(query.problemQuery)
  if (query.problemQuery && !query.resolvedProblemId) {
    message.warning(t('admin.submissions.problemNotFound'))
    return
  }
  resetPage()
  void load()
}

function changeSubmitType(value: unknown): void {
  query.submitType = String(value)
  onSearch()
}

function changeStatus(value: unknown): void {
  query.status = String(value)
  onSearch()
}

function changeLanguage(value: unknown): void {
  query.language = String(value)
  onSearch()
}

function clearProblem(): void {
  query.problemQuery = ''
  query.resolvedProblemId = null
  onSearch()
}

/** 提交查看上下文评测详情（复用评测详情组件；返回与面包屑留在提交查看动线） */
function goDetail(row: AdminSubmission): void {
  router.push(`/admin/submissions/problems/${row.problem_id}/submissions/${row.id}`)
}

/** 行内「查看题目」：提交查看上下文只读预览 */
function goProblem(row: AdminSubmission): void {
  router.push(`/admin/submissions/problems/${row.problem_id}/preview`)
}

const columns = computed<AppTableColumn<AdminSubmission>[]>(() => [
  {
    key: 'problem_id',
    title: t('admin.submissions.problemId'),
    width: '110px',
    cell: (row) =>
      h('code', { class: 'text-[12px] text-muted-foreground' }, `#${row.problem_id.slice(0, 8)}`),
  },
  {
    key: 'problem_title',
    title: t('admin.submissions.problem'),
    cell: (row) => h('span', { class: 'font-medium' }, row.problem_title ?? '—'),
  },
  {

    key: 'nickname',
    title: t('admin.submissions.submitter'),
    width: '140px',
    cell: (row) => h('span', { class: 'text-[13px]' }, row.nickname),
  },
  {
    key: 'status',
    title: t('problems.detail.status'),
    width: '130px',
    cell: (row) => h(StatusTag, { status: row.status }),
  },
  {
    key: 'score',
    title: t('problems.submission.score'),
    width: '76px',
    align: 'right',
    cell: (row) => row.score ?? '-',
    cellClass: 'tabular-nums',
  },
  {
    key: 'time',
    title: t('problems.submission.time'),
    width: '96px',
    align: 'right',
    cell: (row) => `${row.time_used_ms ?? '-'} ms`,
    cellClass: 'tabular-nums text-muted-foreground',
  },
  {
    key: 'memory',
    title: t('problems.submission.memory'),
    width: '104px',
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
      const meta = submitTypeMeta[row.submit_type]
      if (!meta) return row.submit_type
      return h(ToneBadge, { tone: meta.tone, label: t(meta.labelKey) })
    },
  },
  {
    key: 'created_at',
    title: t('problems.submissionsManage.submitTime'),
    width: '160px',
    cell: (row) => formatDateTime(row.created_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
  {
    key: 'actions',
    title: t('action.view'),
    width: '96px',
    cell: (row) =>
      h(
        Button,
        {
          variant: 'ghost',
          size: 'xs',
          onClick: (event: MouseEvent) => {
            event.stopPropagation()
            goProblem(row)
          },
        },
        { default: () => t('admin.submissions.viewProblem') },
      ),
  },
])

onMounted(load)
</script>

<template>
  <WorkbenchShell :title="t('nav.submissionsManage')">
    <template #toolbar>
      <SearchFilterBar
        :keyword="query.keyword"
        :placeholder="t('admin.submissions.searchUser')"
        @update:keyword="query.keyword = $event"
        @search="onSearch"
        @reset="onSearch"
      >
        <Select :model-value="query.submitType" @update:model-value="changeSubmitType">
          <SelectTrigger class="h-9 w-[130px] text-[13px]">
            <SelectValue :placeholder="t('problems.submissionsManage.allTypes')" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{{ t('problems.submissionsManage.allTypes') }}</SelectItem>
            <SelectItem v-for="item in submitTypes" :key="item.value" :value="item.value">
              {{ t(item.labelKey) }}
            </SelectItem>
          </SelectContent>
        </Select>

        <Select :model-value="query.status" @update:model-value="changeStatus">
          <SelectTrigger class="h-9 w-[140px] text-[13px]">
            <SelectValue :placeholder="t('common.allStatus')" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{{ t('common.allStatus') }}</SelectItem>
            <SelectItem v-for="item in statusOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </SelectItem>
          </SelectContent>
        </Select>

        <Select :model-value="query.language" @update:model-value="changeLanguage">
          <SelectTrigger class="h-9 w-[150px] text-[13px]">
            <SelectValue :placeholder="t('problems.submissionsManage.allLanguages')" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{{ t('problems.submissionsManage.allLanguages') }}</SelectItem>
            <SelectItem v-for="item in languageOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </SelectItem>
          </SelectContent>
        </Select>

        <div class="relative w-[200px]">
          <Input
            v-model="query.problemQuery"
            class="h-9 pr-7 text-[13px]"
            :placeholder="t('admin.submissions.problemQuery')"
            :aria-label="t('admin.submissions.problemQuery')"
            @keyup.enter="onSearch"
          />
          <button
            v-if="query.problemQuery"
            type="button"
            class="absolute right-1 top-1/2 grid size-6 -translate-y-1/2 place-items-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            :aria-label="t('action.reset')"
            @click="clearProblem"
          >
            <X class="size-3.5" />
          </button>
        </div>

        <template #actions>
          <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load()" />
        </template>
      </SearchFilterBar>
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
      :empty-text="t('admin.submissions.empty')"
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
