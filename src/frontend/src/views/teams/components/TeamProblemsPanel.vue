<script setup lang="ts">
/**
 * 团队详情 · 团队题库面板：已发布题目表格（搜索 / 分页 / 行点击进团队写题页）。
 * 管理视图带发布验题 / 可见性列与 ⋯ 行操作（编辑 / 归档验题）；引用题目走独立引用页。
 */
import { computed, h, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type { DataTableColumns } from 'naive-ui'
import { CirclePlus, MoreFilled } from '@element-plus/icons-vue'
import { NButton, NDropdown, NIcon, NTag } from 'naive-ui'

import { listTeamProblems } from '@/api/teams'
import { archiveProblem } from '@/api/problems'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { renderDifficulty, renderRatio } from '@/utils/problemCells'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import type { TeamProblemSummary } from '@/types'

const props = defineProps<{
  teamId: string
  isAdmin: boolean
}>()

const { t } = useI18n()
const router = useRouter()

const problems = ref<TeamProblemSummary[]>([])
const problemsLoading = ref(false)
const problemKeyword = ref('')
const {
  page: problemPage,
  pageSize: problemPageSize,
  total: problemTotal,
  changePage: changeProblemPage,
  resetPage: resetProblemPage,
} = usePagination()

async function loadProblems() {
  problemsLoading.value = true
  try {
    const result = await listTeamProblems(props.teamId, {
      page: problemPage.value,
      page_size: problemPageSize.value,
      keyword: problemKeyword.value || undefined,
    })
    problems.value = result.items
    problemTotal.value = result.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    problemsLoading.value = false
  }
}

function searchProblems() {
  resetProblemPage()
  loadProblems()
}

function openTeamProblem(row: TeamProblemSummary) {
  void router.push(`/teams/${props.teamId}/problems/${row.id}`)
}

/** 题库行内操作（⋯ 下拉，仅团队管理可见；backend 仍强校验 owner/admin） */
type ProblemAction = 'edit' | 'archive'

function problemActions(row: TeamProblemSummary): Array<{ key: ProblemAction; label: string }> {
  const actions: Array<{ key: ProblemAction; label: string }> = [
    { key: 'edit', label: t('action.edit') },
  ]
  if (row.status === 'published') {
    actions.push({ key: 'archive', label: t('problems.detail.archive') })
  }
  return actions
}

function onProblemAction(key: ProblemAction, row: TeamProblemSummary) {
  if (key === 'edit') {
    void router.push(`/teams/${props.teamId}/problems/${row.id}/edit/statement`)
    return
  }
  confirmAsyncDialog({
    title: t('problems.detail.archive'),
    content: t('problems.mine.archiveConfirm'),
    positiveText: t('problems.detail.archive'),
    action: async () => {
      await archiveProblem(row.id)
    },
    successMessage: t('problems.detail.archiveSuccess'),
    onAfterSuccess: () => loadProblems(),
  })
}

/** 引用题目页（团队题目 = 引用制；引用门控由团队角色承担，后端强校验） */
function openProblemReference() {
  void router.push(`/teams/${props.teamId}/problems/new`)
}

/** 团队题库列表列（行点击进团队写题页；限制 + 通过率；管理视图带发布验题 / 可见性列） */
const problemColumns = computed<DataTableColumns<TeamProblemSummary>>(() => [
  {
    title: t('problems.list.name'),
    key: 'title',
    minWidth: 200,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'cell-strong' }, row.title),
  },
  ...(props.isAdmin
    ? [
        {
          title: t('problems.manage.shareTitle'),
          key: 'publish',
          width: 110,
          render: (row: TeamProblemSummary) => {
            // 已验题后才可能「需重新验题」（未验题 → 显示未验题）
            if (row.is_verified && row.needs_reverification) {
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
      ]
    : []),
  ...(props.isAdmin
    ? [
        {
          title: t('problems.list.visibility'),
          key: 'visibility',
          width: 96,
          render: (row: TeamProblemSummary) =>
            h(
              NTag,
              {
                size: 'small',
                bordered: false,
                type: row.visibility === 'team_visible' ? 'info' : 'default',
              },
              { default: () => t(`problems.visibility.${row.visibility}`) },
            ),
        },
      ]
    : []),
  {
    title: t('problems.list.difficulty'),
    key: 'difficulty',
    width: 80,
    align: 'center',
    render: (row) => renderDifficulty(row),
  },
  {
    title: t('problems.list.limits'),
    key: 'limits',
    width: 150,
    render: (row) => `${row.time_limit_ms ?? '--'} ms / ${row.memory_limit_mb ?? '--'} MB`,
  },
  {
    title: t('problems.list.passRate'),
    key: 'rate',
    width: 110,
    align: 'center',
    render: (row) => renderRatio(row),
  },
  ...(props.isAdmin
    ? [
        {
          title: '',
          key: 'ops',
          width: 48,
          render: (row: TeamProblemSummary) =>
            h(
              NDropdown,
              {
                trigger: 'click',
                options: problemActions(row).map((a) => ({ key: a.key, label: a.label })),
                onSelect: (key: ProblemAction) => onProblemAction(key, row),
              },
              {
                default: () =>
                  h(
                    NButton,
                    {
                      circle: true,
                      quaternary: true,
                      size: 'tiny',
                      'aria-label': t('teams.detail.more'),
                      // 阻断冒泡：行 onClick 会把点击吞成「进入题目」
                      onClick: (e: MouseEvent) => e.stopPropagation(),
                    },
                    { icon: () => h(NIcon, { component: MoreFilled }) },
                  ),
              },
            ),
        },
      ]
    : []),
])

function rowKeyOfProblem(row: TeamProblemSummary) {
  return row.id
}

function rowPropsOfProblem(row: TeamProblemSummary) {
  return {
    style: 'cursor: pointer;',
    onClick: () => openTeamProblem(row),
  }
}

onMounted(loadProblems)
</script>

<template>
  <SearchFilterBar
    :keyword="problemKeyword"
    :placeholder="t('teams.space.problemSearch')"
    @update:keyword="
      (v: string) => {
        problemKeyword = v
      }
    "
    @search="searchProblems"
    @reset="searchProblems"
  >
    <template #actions>
      <NButton v-if="isAdmin" size="small" type="primary" secondary @click="openProblemReference">
        <template #icon>
          <NIcon :component="CirclePlus" />
        </template>
        {{ t('teams.space.referenceProblem') }}
      </NButton>
      <RefreshButton
        :loading="problemsLoading"
        :aria-label="t('action.refresh')"
        @click="loadProblems"
      />
    </template>
  </SearchFilterBar>
  <PaginatedDataTable
    :columns="problemColumns"
    :data="problems"
    :loading="problemsLoading"
    :total="problemTotal"
    :page="problemPage"
    :page-size="problemPageSize"
    :empty-text="t('teams.space.problemsEmpty')"
    :table-props="{
      size: 'small',
      rowKey: rowKeyOfProblem,
      rowProps: rowPropsOfProblem,
    }"
    @update:page="
      (p: number) => {
        changeProblemPage(p)
        loadProblems()
      }
    "
  />
</template>

<style scoped>
.cell-strong {
  font-weight: 600;
}
</style>
