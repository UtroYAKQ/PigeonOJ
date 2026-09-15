<script setup lang="ts">
/**
 * 团队题目引用页（/teams/:teamId/problems/new）：团队题目 = 引用制
 * （docs/contracts/teams.md 团队空间节），页面即团队的「创建题目」入口。
 * 列出本人已发布题目（mine 视图，tutor / admin 全局身份可引用），点「引用」
 * 归属切换进团队题库。成功后 replace 回团队详情。
 */
import { computed, h, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NButton, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import { referenceTeamProblem, searchTeamReferenceableProblems } from '@/api/teams'
import { message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { useUserStore } from '@/stores/user'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import type { TeamProblemSummary } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const teamId = String(route.params.teamId)

/** 引用能力：tutor / admin 才拥有可引用的全站题目 */
const canReference = computed(() => userStore.hasAnyRole(['admin', 'tutor']))

const items = ref<TeamProblemSummary[]>([])
const loading = ref(false)
const keyword = ref('')
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

async function load() {
  const seq = beginLoad()
  loading.value = true
  try {
    // 候选端点已在服务端排除：他人题、未发布、团队题、已被该团队引用过的源题
    const result = await searchTeamReferenceableProblems(teamId, {
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
    })
    if (!isCurrent(seq)) return
    items.value = result.items
    total.value = result.total
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

function onSearch() {
  resetPage()
  void load()
}

async function onReference(row: TeamProblemSummary) {
  try {
    await referenceTeamProblem(teamId, { problem_id: row.id, visibility: 'team_visible' })
    message.success(t('teams.space.referenceSuccess'))
    void router.replace(`/teams/${teamId}`)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

const columns = computed<DataTableColumns<TeamProblemSummary>>(() => [
  {
    title: t('problems.list.name'),
    key: 'title',
    minWidth: 260,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'cell-strong' }, row.title),
  },
  {
    title: t('problems.list.visibility'),
    key: 'visibility',
    width: 100,
    render(row) {
      // 候选恒为本人全站题（referenceable 端点已排除团队题）；标记公开 / 私有
      const isPublic = (row.visibility as string) === 'public'
      return h(
        NTag,
        { size: 'small', bordered: false, type: isPublic ? 'success' : 'default' },
        {
          default: () => t(isPublic ? 'problems.visibility.public' : 'problems.visibility.private'),
        },
      )
    },
  },
  {
    title: t('problems.list.difficulty'),
    key: 'difficulty',
    width: 90,
    align: 'center',
    render: (row) => ((row.difficulty ?? null) === null ? '--' : String(row.difficulty)),
  },
  {
    title: t('problems.list.limits'),
    key: 'limits',
    width: 160,
    render: (row) => `${row.time_limit_ms ?? '--'} ms / ${row.memory_limit_mb ?? '--'} MB`,
  },
  {
    title: '',
    key: 'actions',
    width: 90,
    render(row) {
      return h(
        NButton,
        { size: 'tiny', type: 'primary', secondary: true, onClick: () => onReference(row) },
        { default: () => t('teams.space.reference') },
      )
    },
  },
])

onMounted(() => {
  if (canReference.value) void load()
})
</script>

<template>
  <WorkbenchShell :title="t('teams.space.referenceProblem')">
    <template #header-extra>
      <n-button size="small" @click="router.replace(`/teams/${teamId}`)">
        {{ t('action.cancel') }}
      </n-button>
    </template>

    <template v-if="canReference">
      <p class="page-hint">{{ t('teams.space.referenceProblemHint') }}</p>
      <SearchFilterBar
        :keyword="keyword"
        :placeholder="t('problems.list.search')"
        @update:keyword="
          (v: string) => {
            keyword = v
          }
        "
        @search="onSearch"
        @reset="onSearch"
      />
      <PaginatedDataTable
        :columns="columns"
        :data="items"
        :loading="loading"
        :total="total"
        :page="page"
        :page-size="pageSize"
        :empty-text="t('teams.space.referenceEmpty')"
        :table-props="{ flexHeight: true, rowKey: (row: TeamProblemSummary) => row.id }"
        @update:page="
          (p: number) => {
            changePage(p)
            load()
          }
        "
      >
        <template #pager-left>
          <span class="pager__total">{{ t('teams.pane.problemTotal', { count: total }) }}</span>
        </template>
      </PaginatedDataTable>
    </template>
    <div v-else class="table-fill-empty">
      <n-empty :description="t('teams.space.referenceNoPermission')" size="large" />
    </div>
  </WorkbenchShell>
</template>

<style scoped>
.page-hint {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.cell-strong {
  font-weight: 600;
}
</style>
