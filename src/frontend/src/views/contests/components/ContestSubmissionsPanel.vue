<script setup lang="ts">
/**
 * 比赛详情 · 提交记录面板：筛选（昵称 / 语言 / 题目 / 状态）+ 分页表格。
 * tab 激活时懒加载；比赛期间仅管理角色（can_manage）可见，赛后对所有登录用户开放
 * （行点击进上下文内评测结果页，frontend.md 路由上下文隔离）。
 */
import { computed, h, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { DataTableColumns } from 'naive-ui'

import { listContestSubmissions } from '@/api/contests'
import { listTeamContestSubmissions } from '@/api/teams'
import { message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import { usePagination } from '@/composables/usePagination'
import { useUserStore } from '@/stores/user'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import { languageOptions } from '@/constants/languages'
import type { ContestDetail, ContestSubmissionItem } from '@/types'

const props = defineProps<{
  detail: ContestDetail
  /** 所属 tab 是否处于激活态（宿主传入，驱动懒加载） */
  active: boolean
}>()

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

/** 比赛 id：全局路由取 params.id，团队上下文路由取 params.cid */
const contestId = computed(() => String(route.params.cid ?? route.params.id))
const teamId = computed(() => (route.params.teamId ? String(route.params.teamId) : null))
/** 上下文基路径（frontend.md 路由上下文隔离）：团队比赛路由内导航不跳出团队前缀 */
const contextBase = computed(() =>
  teamId.value
    ? `/teams/${teamId.value}/contests/${contestId.value}`
    : `/contests/${contestId.value}`,
)

// ---- 提交记录（tab 激活时懒加载；比赛期间仅管理角色可见，赛后对所有登录用户开放） ----
const submissions = ref<ContestSubmissionItem[]>([])
const subsLoading = ref(false)
const {
  page: subsPage,
  pageSize: subsPageSize,
  total: subsTotal,
  changePage,
  changeSize,
  resetPage: subsResetPage,
  beginLoad: subsBeginLoad,
  isCurrent: subsIsCurrent,
} = usePagination()

/** 提交记录筛选条件（昵称关键字 / 语言 / 题目 / 状态，均随请求透传）；
 * 下拉筛选以 null 表示不限——naive-ui n-select 对 '' 会走 fallback 渲染成空串，
 * placeholder（「全部题目」等文字提示）只在 null 时展示 */
const subsQuery = reactive({
  keyword: '',
  language: null as string | null,
  problemId: null as string | null,
  status: null as string | null,
})

/** 比赛期间（end_time 之前）提交记录对参赛者隐藏；管理角色（can_manage，含 admin）随时可见 */
const subsLocked = computed(
  () =>
    !!props.detail &&
    !props.detail.can_manage &&
    Date.now() < new Date(props.detail.end_time).getTime(),
)
/** 赛后向所有登录用户开放（含未报名者）；管理角色随时可见 */
const subsAllowed = computed(() => {
  const d = props.detail
  return (
    !!d && (d.can_manage || (userStore.isLoggedIn && Date.now() >= new Date(d.end_time).getTime()))
  )
})

async function loadSubmissions(silent = false) {
  const seq = subsBeginLoad()
  subsLoading.value = !silent
  try {
    const query = {
      page: subsPage.value,
      page_size: subsPageSize.value,
      keyword: subsQuery.keyword || undefined,
      language: subsQuery.language || undefined,
      problem_id: subsQuery.problemId || undefined,
      status: subsQuery.status || undefined,
    }
    const result = await (teamId.value
      ? listTeamContestSubmissions(teamId.value, contestId.value, query)
      : listContestSubmissions(contestId.value, query))
    if (!subsIsCurrent(seq)) return
    submissions.value = result.items
    subsTotal.value = result.total
  } catch (error) {
    if (!subsIsCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (subsIsCurrent(seq)) subsLoading.value = false
  }
}

/** 筛选条件变更：回第一页重新加载 */
function onSubsSearch() {
  subsResetPage()
  void loadSubmissions()
}

watch(
  () => props.active,
  (active) => {
    if (active && !subsLocked.value && subsAllowed.value && !submissions.value.length) {
      void loadSubmissions()
    }
  },
)

/** 题目筛选选项（比赛题目，题号 + 标题；详情携带题目时才可筛选） */
const subsProblemOptions = computed(() =>
  (props.detail.problems ?? []).map((p) => ({
    value: p.problem_id,
    label: p.letter ? `${p.letter} · ${p.title}` : p.title,
  })),
)

/** 语言筛选选项（复用判题语言字典；空值「全部语言」由 clearable placeholder 承担） */
const subsLanguageOptions = languageOptions.map((option) => ({
  label: option.label,
  value: option.value,
}))

/** 状态筛选选项（常用结果；标签复用 problems.status 字典） */
const subsStatusOptions = [
  { value: 'accepted', labelKey: 'problems.status.accepted' },
  { value: 'wrong_answer', labelKey: 'problems.status.wrong_answer' },
  { value: 'compile_error', labelKey: 'problems.status.compile_error' },
].map((option) => ({ value: option.value, label: t(option.labelKey) }))

function changeSubsPage(value: number) {
  changePage(value)
  void loadSubmissions()
}

function changeSubsPageSize(value: number) {
  changeSize(value)
  void loadSubmissions()
}

function openSubmission(row: ContestSubmissionItem) {
  router.push(`${contextBase.value}/submissions/${row.id}`)
}

function submissionRowProps(row: ContestSubmissionItem) {
  return {
    style: 'cursor: pointer;',
    onClick: () => openSubmission(row),
  }
}

const submissionColumns = computed<DataTableColumns<ContestSubmissionItem>>(() => {
  // ACM 二值分（AC=满分否则 0）不是部分分，提交记录不展示分数列（IOI 才有意义）
  const cols: DataTableColumns<ContestSubmissionItem> = [
    {
      title: t('contests.detail.letter'),
      key: 'letter',
      width: 70,
      render: (row) => row.letter ?? '--',
    },
    {
      title: t('contests.submissions.user'),
      key: 'nickname',
      minWidth: 120,
    },
    {
      title: t('problems.detail.status'),
      key: 'status',
      minWidth: 150,
      render: (row) => h(StatusTag, { status: row.status }),
    },
  ]
  if (props.detail.rule_type !== 'ACM') {
    cols.push({
      title: t('problems.submission.score'),
      key: 'score',
      width: 80,
      render: (row) => row.score ?? '-',
    })
  }
  cols.push(
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
      title: t('contests.submissions.submitTime'),
      key: 'created_at',
      width: 170,
      render: (row) => formatDateTime(row.created_at),
    },
  )
  return cols
})
</script>

<template>
  <n-alert v-if="subsLocked" type="info" :bordered="false" class="subs-hint">
    {{ t('contests.submissions.hiddenDuringContest') }}
  </n-alert>
  <n-alert v-else-if="!subsAllowed" type="info" :bordered="false" class="subs-hint">
    {{ t('contests.submissions.loginRequired') }}
  </n-alert>
  <template v-else>
    <SearchFilterBar
      :keyword="subsQuery.keyword"
      :placeholder="t('contests.submissions.search')"
      @update:keyword="
        (v: string) => {
          subsQuery.keyword = v
        }
      "
      @search="onSubsSearch"
      @reset="onSubsSearch"
    >
      <n-select
        v-model:value="subsQuery.problemId"
        clearable
        filterable
        style="width: 200px"
        :options="subsProblemOptions"
        :placeholder="t('contests.submissions.allProblems')"
        @update:value="onSubsSearch"
      />
      <n-select
        v-model:value="subsQuery.language"
        clearable
        style="width: 150px"
        :options="subsLanguageOptions"
        :placeholder="t('contests.submissions.allLanguages')"
        @update:value="onSubsSearch"
      />
      <n-select
        v-model:value="subsQuery.status"
        clearable
        style="width: 130px"
        :options="subsStatusOptions"
        :placeholder="t('common.allStatus')"
        @update:value="onSubsSearch"
      />
    </SearchFilterBar>
    <PaginatedDataTable
      :columns="submissionColumns"
      :data="submissions"
      :loading="subsLoading"
      :total="subsTotal"
      v-model:page="subsPage"
      v-model:page-size="subsPageSize"
      :empty-text="t('contests.submissions.empty')"
      :table-props="{ scrollX: 900, flexHeight: true, rowProps: submissionRowProps }"
      @update:page="changeSubsPage"
      @update:page-size="changeSubsPageSize"
    >
      <template #pager-left>
        <span class="pager__total">
          {{ t('contests.submissions.totalCount', { count: subsTotal }) }}
        </span>
      </template>
    </PaginatedDataTable>
  </template>
</template>

<style scoped>
.subs-hint {
  margin-bottom: 10px;
}
</style>
