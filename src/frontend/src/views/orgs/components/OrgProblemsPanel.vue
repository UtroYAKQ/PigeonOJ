<script setup lang="ts">
/**
 * 组织详情 · 组织题库面板：题目表格（搜索 / 草稿箱 / 分页）。
 * 组织题库为封闭上下文——列表走组织端点，题目编辑复用题库统一端点
 * （行点击：已发布题进组织作答页，草稿进编辑向导；创建走组织端点）。
 */
import { computed, h, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { Collection, MoreFilled } from '@element-plus/icons-vue'
import type { DataTableColumns } from 'naive-ui'
import { NButton, NCheckbox, NDropdown, NIcon, NTag } from 'naive-ui'

import { listOrgProblems } from '@/api/orgs'
import { message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { renderDifficulty, renderRatio } from '@/utils/problemCells'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import type { TeamProblemSummary } from '@/types'

const props = defineProps<{
  orgId: string
  isMember: boolean
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
    const result = await listOrgProblems(props.orgId, {
      page: problemPage.value,
      page_size: problemPageSize.value,
      keyword: problemKeyword.value || undefined,
      status: draftOnly.value ? 'draft' : undefined,
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

/** 草稿箱勾选：勾选后列表查询全组织草稿题目（后端 status=draft 过滤） */
const draftOnly = ref(false)

function onToggleDraftBox(checked: boolean) {
  draftOnly.value = checked
  resetProblemPage()
  loadProblems()
}

/** 创建题目（组织成员 my_role 非空）：进组织题目创建向导（POST /orgs/{orgId}/problems） */
function openProblemCreate() {
  void router.push(`/me/orgs/${props.orgId}/problems/new`)
}

/** 行点击：已发布题进组织作答页（组织成员可交题 / 自测，docs/contracts/orgs.md）；
 * 草稿进编辑向导（草稿不可作答）。 */
function openOrgProblem(row: TeamProblemSummary) {
  const base = `/me/orgs/${props.orgId}/problems/${row.id}`
  void router.push(row.status === 'published' ? base : `${base}/edit/statement`)
}

/** 题库行内操作（⋯ 下拉）：组织成员均具组织题库写权（org_member），草稿 / 已发布均可编辑 */
type ProblemRowAction = 'edit'

function problemRowActions(): Array<{ key: ProblemRowAction; label: string }> {
  return [{ key: 'edit', label: t('action.edit') }]
}

function onProblemRowAction(key: ProblemRowAction, row: TeamProblemSummary) {
  if (key === 'edit') {
    void router.push(`/me/orgs/${props.orgId}/problems/${row.id}/edit/statement`)
  }
}

const problemColumns = computed<DataTableColumns<TeamProblemSummary>>(() => [
  {
    title: t('problems.list.name'),
    key: 'title',
    minWidth: 200,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'cell-strong' }, row.title),
  },
  {
    title: t('problems.manage.shareTitle'),
    key: 'publish',
    width: 110,
    render: (row) => {
      // 已验题后才可能「需重新验题」（草稿从未验题 → 显示未验题）
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
            row.is_verified ? t('problems.manage.verifiedTag') : t('problems.manage.unverifiedTag'),
        },
      )
    },
  },
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
  {
    title: '',
    key: 'ops',
    width: 48,
    render: (row: TeamProblemSummary) =>
      h(
        NDropdown,
        {
          trigger: 'click',
          options: problemRowActions().map((a) => ({ key: a.key, label: a.label })),
          onSelect: (key: ProblemRowAction) => onProblemRowAction(key, row),
        },
        {
          default: () =>
            h(
              NButton,
              {
                circle: true,
                quaternary: true,
                size: 'tiny',
                'aria-label': t('orgs.detail.more'),
                // 阻断冒泡：行 onClick 会把点击吞成「进入题目 / 进编辑向导」
                onClick: (e: MouseEvent) => e.stopPropagation(),
              },
              { icon: () => h(NIcon, { component: MoreFilled }) },
            ),
        },
      ),
  },
])

onMounted(loadProblems)
</script>

<template>
  <SearchFilterBar
    :keyword="problemKeyword"
    :placeholder="t('orgs.problems.search')"
    @update:keyword="
      (v: string) => {
        problemKeyword = v
      }
    "
    @search="searchProblems"
    @reset="searchProblems"
  >
    <template #actions>
      <NButton v-if="isMember" size="small" secondary @click="openProblemCreate">
        <template #icon>
          <NIcon :component="Collection" />
        </template>
        {{ t('orgs.problems.create') }}
      </NButton>
      <NCheckbox :checked="draftOnly" @update:checked="onToggleDraftBox">
        {{ t('orgs.problems.draftBox') }}
      </NCheckbox>
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
    :empty-text="t(draftOnly ? 'orgs.problems.draftsEmpty' : 'orgs.problems.empty')"
    :table-props="{
      size: 'small',
      rowKey: (row: TeamProblemSummary) => row.id,
      rowProps: (row: TeamProblemSummary) => ({
        style: 'cursor: pointer;',
        onClick: () => openOrgProblem(row),
      }),
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
