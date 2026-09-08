<script setup lang="ts">
/**
 * 比赛管理（管理后台，admin/tutor；docs/contracts/contests.md）：
 * 全量比赛列表；行点击进入编辑页，创建走全页表单（/admin/contests/create）。
 * 行内「⋯」：管理比赛 / 赛时工具（公告 / 赛后解榜 / 滚榜大屏）。
 * 比赛开始后结构性字段被后端守卫锁定，赛时调整收敛到工具页。
 */
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { MoreFilled } from '@element-plus/icons-vue'
import { NButton, NDropdown, NIcon, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import RefreshButton from '@/components/RefreshButton.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { adminListContests } from '@/api/admin'
import { message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { formatDateTime } from '@/utils/format'
import type { ContestSummary, PageResult } from '@/types'

const router = useRouter()
const { t } = useI18n()
const loading = ref(false)
const rows = ref<ContestSummary[]>([])
const { page, pageSize, total, changePage, changeSize, beginLoad, isCurrent } = usePagination()
const keyword = ref('')
const contestType = ref<'' | 'public' | 'team'>('')

/** 类型筛选项：公开 / 团队（缺省 = 全量） */
const typeOptions = computed(() => [
  { label: t('contests.list.typePublic'), value: 'public' },
  { label: t('contests.list.typeTeam'), value: 'team' },
])

function switchType(value: string | null) {
  contestType.value = (value ?? '') as '' | 'public' | 'team'
  changePage(1)
  load()
}

async function load() {
  const seq = beginLoad()
  loading.value = true
  try {
    const result: PageResult<ContestSummary> = await adminListContests({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      contest_type: contestType.value || undefined,
    })
    if (!isCurrent(seq)) return
    rows.value = result.items
    total.value = result.total
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

onMounted(load)

const statusMap = computed(() => ({
  running: { label: t('contests.statusRunning'), type: 'success' as const },
  scheduled: { label: t('contests.statusScheduled'), type: 'info' as const },
  finished: { label: t('contests.statusFinished'), type: 'default' as const },
}))

const columns = computed<DataTableColumns<ContestSummary>>(() => [
  {
    title: t('contests.list.titleLabel'),
    key: 'title',
    minWidth: 260,
    render(row) {
      return h('div', { class: 'contest-name' }, [h('strong', null, row.title)])
    },
  },
  { title: t('contests.list.ruleType'), key: 'rule_type', width: 80 },
  {
    title: t('contests.list.type'),
    key: 'contest_type',
    width: 80,
    render: (row) =>
      h(
        NTag,
        { size: 'small', bordered: false, type: row.contest_type === 'team' ? 'warning' : 'info' },
        {
          default: () =>
            t(row.contest_type === 'team' ? 'contests.list.typeTeam' : 'contests.list.typePublic'),
        },
      ),
  },
  {
    title: t('contests.statusRunning'),
    key: 'status',
    width: 100,
    render: (row) =>
      h(
        NTag,
        { size: 'small', bordered: false, type: statusMap.value[row.status].type },
        { default: () => statusMap.value[row.status].label },
      ),
  },
  {
    title: t('contests.list.startTime'),
    key: 'start_time',
    width: 170,
    render: (row) => formatDateTime(row.start_time),
  },
  {
    title: t('contests.list.endTime'),
    key: 'end_time',
    width: 170,
    render: (row) => formatDateTime(row.end_time),
  },
  {
    title: t('contests.detail.problems'),
    key: 'problem_count',
    width: 90,
    render: (row) => t('contests.list.problemCount', { count: row.problem_count }),
  },
  {
    title: '',
    key: 'ops',
    width: 48,
    render: (row) =>
      h(
        NDropdown,
        {
          trigger: 'click',
          options: [
            {
              key: 'manage',
              label: t('contests.detail.manage'),
              disabled: row.status !== 'scheduled',
            },
            { key: 'tools', label: t('contests.tools.title') },
          ],
          onSelect: (key: string | number) => {
            if (key === 'tools') {
              void router.push(`/admin/contests/${row.id}/tools`)
              return
            }
            if (row.status !== 'scheduled') return
            void router.push(`/admin/contests/${row.id}/edit/basic`)
          },
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
                onClick: (event: MouseEvent) => event.stopPropagation(),
              },
              { icon: () => h(NIcon, { component: MoreFilled }) },
            ),
        },
      ),
  },
])

/** 赛前点进编辑向导；开赛后进赛时工具 */
function rowProps(row: ContestSummary) {
  return {
    style: 'cursor: pointer;',
    onClick: () =>
      router.push(
        row.status === 'scheduled'
          ? `/admin/contests/${row.id}/edit/basic`
          : `/admin/contests/${row.id}/tools`,
      ),
  }
}
</script>

<template>
  <WorkbenchShell>
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('contests.list.search')"
      search-width="260px"
      manual
      @update:keyword="
        (v: string) => {
          keyword = v
        }
      "
      @search="load"
      @reset="load"
    >
      <n-select
        :value="contestType || null"
        clearable
        style="width: 140px"
        :options="typeOptions"
        :placeholder="t('contests.list.typeAll')"
        @update:value="switchType"
      />
      <template #actions>
        <n-button type="primary" size="small" @click="router.push('/admin/contests/create')">
          {{ t('contests.list.create') }}
        </n-button>
        <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
      </template>
    </SearchFilterBar>

    <PaginatedDataTable
      :columns="columns"
      :data="rows"
      :loading="loading"
      :total="total"
      v-model:page="page"
      v-model:page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      :empty-text="t('contests.list.empty')"
      :table-props="{ rowProps }"
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
        <span class="pager__total">{{ t('contests.list.totalCount', { count: total }) }}</span>
      </template>
    </PaginatedDataTable>
  </WorkbenchShell>
</template>

<style scoped>
.contest-name {
  display: grid;
  gap: 4px;
}
.contest-name strong {
  font-size: 14px;
}
.contest-name span {
  color: var(--app-text-secondary);
  font-size: 12px;
}
</style>
