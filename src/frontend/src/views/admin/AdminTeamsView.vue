<script setup lang="ts">
/**
 * 团队管理（管理后台，admin；docs/contracts/teams.md 管理端）：
 * 全量团队列表（含已解散）+ 「指派组织」动作（PUT /admin/teams/{id}/org，
 * 存量团队迁移用——组织化改造后团队创建入口收敛在组织空间，引用题目需归属组织）；
 * 行整行点击进入团队详情（成员 / 团队题库 / 团队题单 / 团队比赛只读浏览）。
 */
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NButton, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import { adminAssignTeamOrg, adminListOrgs, adminListTeams } from '@/api/admin'
import BaseAvatar from '@/components/BaseAvatar.vue'
import { message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { formatDateTime } from '@/utils/format'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import type { OrgSummary, TeamAdminSummary } from '@/types'

const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const list = ref<TeamAdminSummary[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()
const keyword = ref('')
const statusFilter = ref<'active' | 'disbanded' | null>(null)

async function load() {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await adminListTeams({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      status: statusFilter.value ?? undefined,
    })
    if (!isCurrent(seq)) return
    list.value = result.items
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
  load()
}

onMounted(load)

const statusOptions = computed(() => [
  { label: t('common.allStatus'), value: 'all' },
  { label: t('admin.teams.statusActive'), value: 'active' },
  { label: t('admin.teams.statusDisbanded'), value: 'disbanded' },
])
const statusValue = computed({
  get: () => statusFilter.value ?? 'all',
  set: (v: string) => {
    statusFilter.value = v === 'all' ? null : (v as 'active' | 'disbanded')
    onSearch()
  },
})

const columns = computed<DataTableColumns<TeamAdminSummary>>(() => [
  {
    // 头像独立一列（圆形 36px），与名称列拉开间距
    title: t('admin.teams.avatar'),
    key: 'avatar_url',
    width: 72,
    align: 'center',
    render(row) {
      return h(BaseAvatar, { src: row.avatar_url, name: row.name, size: 36, kind: 'team' })
    },
  },
  {
    title: t('admin.teams.team'),
    key: 'name',
    minWidth: 200,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'cell-name' }, row.name),
  },
  {
    title: t('admin.teams.creator'),
    key: 'creator_nickname',
    width: 140,
    ellipsis: { tooltip: true },
    render: (row) => row.creator_nickname ?? '—',
  },
  {
    title: t('admin.teams.memberCount'),
    key: 'member_count',
    width: 80,
    align: 'center',
    render: (row) => String(row.member_count),
  },
  {
    title: t('admin.teams.statProblems'),
    key: 'problem_count',
    width: 90,
    align: 'center',
    render: (row) => String(row.problem_count),
  },
  {
    title: t('admin.teams.statSets'),
    key: 'problem_set_count',
    width: 70,
    align: 'center',
    render: (row) => String(row.problem_set_count),
  },
  {
    title: t('admin.teams.statContests'),
    key: 'contest_count',
    width: 70,
    align: 'center',
    render: (row) => String(row.contest_count),
  },
  {
    title: t('admin.teams.status'),
    key: 'status',
    width: 96,
    render(row) {
      const active = row.status === 'active'
      return h(
        NTag,
        { size: 'small', bordered: false, type: active ? 'success' : 'error' },
        { default: () => t(active ? 'admin.teams.statusActive' : 'admin.teams.statusDisbanded') },
      )
    },
  },
  {
    title: t('admin.teams.createdAt'),
    key: 'created_at',
    width: 170,
    render: (row) => formatDateTime(row.created_at),
  },
  {
    // 指派组织（迁移用；阻断冒泡：行 onClick 会吞成「进入团队详情」）
    title: '',
    key: 'ops',
    width: 100,
    render(row) {
      return h(
        NButton,
        {
          size: 'tiny',
          secondary: true,
          onClick: (e: MouseEvent) => {
            e.stopPropagation()
            openAssign(row)
          },
        },
        { default: () => t('admin.teams.assignOrg') },
      )
    },
  },
])

/** 编辑 / 成员维护在团队空间完成；管理端整行点击进入只读详情 */
function rowProps(row: TeamAdminSummary) {
  return { style: 'cursor: pointer;', onClick: () => router.push(`/admin/teams/${row.id}`) }
}

// ---- 指派组织（PUT /admin/teams/{id}/org；组织选项经管理端组织列表拉取） ----

const showAssign = ref(false)
const assigning = ref(false)
const assignTarget = ref<TeamAdminSummary | null>(null)
const assignOrgId = ref<string | null>(null)
const orgs = ref<OrgSummary[]>([])
const orgsLoading = ref(false)

const orgOptions = computed(() =>
  orgs.value.map((org) => ({
    label: `${org.name}（${t('admin.orgs.memberCount')} ${org.member_count}）`,
    value: org.id,
  })),
)

async function openAssign(row: TeamAdminSummary) {
  assignTarget.value = row
  assignOrgId.value = null
  showAssign.value = true
  if (!orgs.value.length) {
    orgsLoading.value = true
    try {
      // 活跃组织全量（存量团队只能指派到 active 组织）；上限取 200 供选择
      const result = await adminListOrgs({ page: 1, page_size: 200, status: 'active' })
      orgs.value = result.items
    } catch (error) {
      message.error(error instanceof Error ? error.message : t('common.loadFailed'))
    } finally {
      orgsLoading.value = false
    }
  }
}

async function doAssign() {
  if (!assignTarget.value || !assignOrgId.value) {
    message.warning(t('admin.teams.assignOrgRequired'))
    return
  }
  assigning.value = true
  try {
    await adminAssignTeamOrg(assignTarget.value.id, assignOrgId.value)
    message.success(t('admin.teams.assignOrgSuccess'))
    showAssign.value = false
    load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    assigning.value = false
  }
}
</script>

<template>
  <WorkbenchShell>
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('admin.teams.search')"
      search-width="260px"
      manual
      @update:keyword="
        (v: string) => {
          keyword = v
        }
      "
      @search="onSearch"
      @reset="onSearch"
    >
      <n-select
        v-model:value="statusValue"
        style="width: 130px"
        :options="statusOptions"
        :aria-label="t('admin.teams.status')"
      />
      <template #actions>
        <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
      </template>
    </SearchFilterBar>

    <PaginatedDataTable
      show-size-picker
      :columns="columns"
      :data="list"
      :loading="loading"
      :total="total"
      v-model:page="page"
      v-model:page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      :empty-text="t('admin.teams.empty')"
      :table-props="{ rowProps, scrollX: 1200 }"
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
        <span class="pager__total">{{ t('admin.teams.totalCount', { count: total }) }}</span>
      </template>
    </PaginatedDataTable>

    <!-- 指派组织（存量团队迁移用；组织创建在组织管理 / 组织中心进行） -->
    <n-modal
      v-model:show="showAssign"
      :title="t('admin.teams.assignOrgTitle')"
      preset="card"
      style="width: 440px"
    >
      <p class="assign-hint">
        {{
          t('admin.teams.assignOrgHint', {
            name: assignTarget?.name ?? '',
          })
        }}
      </p>
      <n-select
        v-model:value="assignOrgId"
        :options="orgOptions"
        :loading="orgsLoading"
        filterable
        clearable
        :placeholder="t('admin.orgs.org')"
      />
      <template #footer>
        <div class="assign-footer">
          <n-button size="small" quaternary @click="showAssign = false">
            {{ t('action.cancel') }}
          </n-button>
          <n-button size="small" type="primary" :loading="assigning" @click="doAssign">
            {{ t('action.confirm') }}
          </n-button>
        </div>
      </template>
    </n-modal>
  </WorkbenchShell>
</template>

<style scoped>
.cell-name {
  font-weight: 600;
  color: var(--app-text);
}
.assign-hint {
  margin: 0 0 10px;
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}
.assign-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
