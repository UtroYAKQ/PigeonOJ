<script setup lang="ts">
/**
 * 团队详情 · 团队题单面板：题单表格（搜索 / 分页 / 行点击进团队题单详情）。
 * 编排 / 下线收敛在 ⋯ 行内下拉（仅团队管理可见）；新建题单收敛到题单创建页。
 */
import { computed, h, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type { DataTableColumns } from 'naive-ui'
import { CirclePlus, MoreFilled } from '@element-plus/icons-vue'
import { NButton, NDropdown, NIcon } from 'naive-ui'

import { archiveTeamProblemSet, listTeamProblemSets } from '@/api/teams'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import type { ProblemSetSummary } from '@/types'

const props = defineProps<{
  teamId: string
  isAdmin: boolean
}>()

const { t } = useI18n()
const router = useRouter()

const sets = ref<ProblemSetSummary[]>([])
const setsLoading = ref(false)
const setKeyword = ref('')
const {
  page: setPage,
  pageSize: setPageSize,
  total: setTotal,
  changePage: changeSetPage,
  resetPage: resetSetPage,
} = usePagination()

async function loadSets() {
  setsLoading.value = true
  try {
    const result = await listTeamProblemSets(props.teamId, {
      page: setPage.value,
      page_size: setPageSize.value,
      keyword: setKeyword.value || undefined,
    })
    sets.value = result.items
    setTotal.value = result.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    setsLoading.value = false
  }
}

function searchSets() {
  resetSetPage()
  loadSets()
}

/** 新建题单收敛到题单创建页（创建 / 编排由团队创建者 / 管理员执行） */
function openSetCreate() {
  void router.push(`/teams/${props.teamId}/sets/new`)
}

async function onArchiveSet(row: ProblemSetSummary) {
  confirmAsyncDialog({
    title: t('teams.space.archiveSet'),
    content: t('teams.space.archiveSetConfirm', { title: row.title }),
    positiveText: t('teams.space.archiveSet'),
    action: async () => {
      await archiveTeamProblemSet(props.teamId, row.id)
    },
    successMessage: t('teams.space.setArchived'),
    onAfterSuccess: () => {
      loadSets()
    },
  })
}

/** 题单行内操作（⋯ 下拉，仅团队管理可见）：编排 / 下线 */
type SetAction = 'arrange' | 'archive'

function setActions(row: ProblemSetSummary): Array<{ key: SetAction; label: string }> {
  const actions: Array<{ key: SetAction; label: string }> = [
    { key: 'arrange', label: t('teams.space.arrange') },
  ]
  if (row.status === 'active') {
    actions.push({ key: 'archive', label: t('teams.space.archiveSet') })
  }
  return actions
}

function onSetAction(key: SetAction, row: ProblemSetSummary) {
  if (key === 'arrange') {
    void router.push(`/teams/${props.teamId}/sets/${row.id}/arrange`)
    return
  }
  void onArchiveSet(row)
}

/** 团队题单列表列（行点击进团队题单详情；编排 / 下线收敛在 ⋯ 下拉） */
const setColumns = computed<DataTableColumns<ProblemSetSummary>>(() => [
  {
    title: t('problemSets.list.titleLabel'),
    key: 'title',
    minWidth: 220,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'cell-strong' }, row.title),
  },
  {
    title: t('admin.teams.setVisible'),
    key: 'item_count',
    width: 80,
    align: 'center',
    render: (row) => String(row.item_count),
  },
  ...(props.isAdmin
    ? [
        {
          title: '',
          key: 'ops',
          width: 48,
          render: (row: ProblemSetSummary) =>
            h(
              NDropdown,
              {
                trigger: 'click',
                options: setActions(row).map((a) => ({ key: a.key, label: a.label })),
                onSelect: (key: SetAction) => onSetAction(key, row),
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
                      // 阻断冒泡：行 onClick 会把点击吞成「进入题单详情」
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

function rowKeyOfSet(row: ProblemSetSummary) {
  return row.id
}

function rowPropsOfSet(row: ProblemSetSummary) {
  return {
    style: 'cursor: pointer;',
    onClick: () => router.push(`/teams/${props.teamId}/sets/${row.id}`),
  }
}

onMounted(loadSets)
</script>

<template>
  <SearchFilterBar
    :keyword="setKeyword"
    :placeholder="t('problemSets.list.search')"
    @update:keyword="
      (v: string) => {
        setKeyword = v
      }
    "
    @search="searchSets"
    @reset="searchSets"
  >
    <template #actions>
      <NButton v-if="isAdmin" size="small" type="primary" @click="openSetCreate">
        <template #icon>
          <NIcon :component="CirclePlus" />
        </template>
        {{ t('teams.space.createSet') }}
      </NButton>
      <RefreshButton :loading="setsLoading" :aria-label="t('action.refresh')" @click="loadSets" />
    </template>
  </SearchFilterBar>
  <PaginatedDataTable
    :columns="setColumns"
    :data="sets"
    :loading="setsLoading"
    :total="setTotal"
    :page="setPage"
    :page-size="setPageSize"
    :empty-text="t('teams.space.setsEmpty')"
    :table-props="{
      size: 'small',
      rowKey: rowKeyOfSet,
      rowProps: rowPropsOfSet,
    }"
    @update:page="
      (p: number) => {
        changeSetPage(p)
        loadSets()
      }
    "
  />
</template>

<style scoped>
.cell-strong {
  font-weight: 600;
}
</style>
