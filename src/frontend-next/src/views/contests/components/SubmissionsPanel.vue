<script setup lang="ts">
import { computed, h, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Info } from '@lucide/vue'

import { listContestSubmissions } from '@/api/contests'
import { listTeamContestSubmissions } from '@/api/teams'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import InlineNotice from '@/components/common/InlineNotice.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import StatusTag from '@/components/common/StatusTag.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { languageOptions } from '@/constants/languages'
import { usePagination } from '@/composables/usePagination'
import { useUserStore } from '@/stores/user'
import { message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { ContestDetail, ContestSubmissionItem } from '@/types'

const props = defineProps<{
  detail: ContestDetail
  teamId: string | null
  contextBase: string
  active: boolean
}>()

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const submissions = ref<ContestSubmissionItem[]>([])
const subsLoading = ref(false)
const loaded = ref(false)
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

const query = reactive({
  keyword: '',
  language: 'all',
  problemId: 'all',
  status: 'all',
})

/** 比赛期间（end_time 之前）提交记录对参赛者隐藏；管理角色随时可见 */
const subsLocked = computed(
  () => !props.detail.can_manage && Date.now() < new Date(props.detail.end_time).getTime(),
)
/** 赛后向所有登录用户开放（含未报名者）；管理角色随时可见 */
const subsAllowed = computed(
  () =>
    props.detail.can_manage ||
    (userStore.isLoggedIn && Date.now() >= new Date(props.detail.end_time).getTime()),
)

const problemOptions = computed(() =>
  props.detail.problems.map((problem) => ({
    value: problem.problem_id,
    label: problem.letter ? `${problem.letter} · ${problem.title}` : problem.title,
  })),
)

const statusOptions = computed(() => [
  { value: 'accepted', label: t('problems.status.accepted') },
  { value: 'wrong_answer', label: t('problems.status.wrong_answer') },
  { value: 'compile_error', label: t('problems.status.compile_error') },
])

const columns = computed<AppTableColumn<ContestSubmissionItem>[]>(() => {
  const list: AppTableColumn<ContestSubmissionItem>[] = [
    {
      key: 'letter',
      title: t('contests.detail.letter'),
      width: '64px',
      align: 'center',
      cell: (row) => row.letter ?? '--',
      cellClass: 'tabular-nums text-muted-foreground',
    },
    {
      key: 'nickname',
      title: t('contests.submissions.user'),
      width: '150px',
      cell: (row) => row.nickname,
      cellClass: 'font-medium',
    },
    {
      key: 'status',
      title: t('problems.detail.status'),
      width: '130px',
      cell: (row) => h(StatusTag, { status: row.status }),
    },
  ]
  if (props.detail.rule_type !== 'ACM') {
    list.push({
      key: 'score',
      title: t('problems.submission.score'),
      width: '72px',
      align: 'right',
      cell: (row) => row.score ?? '-',
      cellClass: 'tabular-nums',
    })
  }
  list.push(
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
      key: 'created_at',
      title: t('contests.submissions.submitTime'),
      width: '170px',
      cell: (row) => formatDateTime(row.created_at),
      cellClass: 'text-[12.5px] text-muted-foreground',
    },
  )
  return list
})

async function load(silent = false): Promise<void> {
  const seq = beginLoad()
  subsLoading.value = !silent
  try {
    const result = await (props.teamId
      ? listTeamContestSubmissions(props.teamId, props.detail.id, {
          page: page.value,
          page_size: pageSize.value,
          keyword: query.keyword || undefined,
          language: query.language === 'all' ? undefined : query.language,
          problem_id: query.problemId === 'all' ? undefined : query.problemId,
          status: query.status === 'all' ? undefined : query.status,
        })
      : listContestSubmissions(props.detail.id, {
          page: page.value,
          page_size: pageSize.value,
          keyword: query.keyword || undefined,
          language: query.language === 'all' ? undefined : query.language,
          problem_id: query.problemId === 'all' ? undefined : query.problemId,
          status: query.status === 'all' ? undefined : query.status,
        }))
    if (!isCurrent(seq)) return
    submissions.value = result.items
    total.value = result.total
    loaded.value = true
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (isCurrent(seq)) subsLoading.value = false
  }
}

function onSearch(): void {
  resetPage()
  void load()
}

function openSubmission(row: ContestSubmissionItem): void {
  void router.push(`${props.contextBase}/submissions/${row.id}`)
}

function onPageChange(value: number): void {
  if (value === page.value) return
  changePage(value)
  void load()
}

watch(
  [() => props.active, subsAllowed],
  () => {
    if (props.active && subsAllowed.value && !loaded.value) void load()
  },
  { immediate: true },
)
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col gap-2.5">
    <InlineNotice v-if="subsLocked" :icon="Info">
      {{ t('contests.submissions.hiddenDuringContest') }}
    </InlineNotice>
    <InlineNotice v-else-if="!subsAllowed" :icon="Info">
      {{ t('contests.submissions.loginRequired') }}
    </InlineNotice>

    <template v-else>
      <SearchFilterBar
        :keyword="query.keyword"
        :placeholder="t('contests.submissions.search')"
        @update:keyword="query.keyword = $event"
        @search="onSearch"
        @reset="onSearch"
      >
        <Select v-model="query.problemId" @update:model-value="onSearch">
          <SelectTrigger class="h-9 w-[190px] text-[13px]">
            <SelectValue :placeholder="t('contests.submissions.allProblems')" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{{ t('contests.submissions.allProblems') }}</SelectItem>
            <SelectItem v-for="item in problemOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </SelectItem>
          </SelectContent>
        </Select>

        <Select v-model="query.language" @update:model-value="onSearch">
          <SelectTrigger class="h-9 w-[150px] text-[13px]">
            <SelectValue :placeholder="t('contests.submissions.allLanguages')" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{{ t('contests.submissions.allLanguages') }}</SelectItem>
            <SelectItem v-for="item in languageOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </SelectItem>
          </SelectContent>
        </Select>

        <Select v-model="query.status" @update:model-value="onSearch">
          <SelectTrigger class="h-9 w-[132px] text-[13px]">
            <SelectValue :placeholder="t('common.allStatus')" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{{ t('common.allStatus') }}</SelectItem>
            <SelectItem v-for="item in statusOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </SelectItem>
          </SelectContent>
        </Select>

        <template #actions>
          <RefreshButton :loading="subsLoading" :label="t('action.refresh')" @click="load()" />
        </template>
      </SearchFilterBar>

      <PaginatedTable
        :columns="columns"
        :data="submissions"
        :loading="subsLoading"
        :total="total"
        :page="page"
        :page-size="pageSize"
        :empty-text="t('contests.submissions.empty')"
        :row-click="openSubmission"
        @update:page="onPageChange"
      >
        <template #pager-left>
          <span class="tabular-nums">
            {{ t('contests.submissions.totalCount', { count: total }) }}
          </span>
        </template>
      </PaginatedTable>
    </template>
  </div>
</template>
