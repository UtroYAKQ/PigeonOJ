<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { adminAssignTeamOrg, adminDisbandTeam, adminListOrgs, adminListTeams } from '@/api/admin'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import RowActions from '@/components/teams/RowActions.vue'
import type { RowAction } from '@/components/teams/types'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { usePagination } from '@/composables/usePagination'
import { confirmDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { OrgDetail, TeamAdminSummary } from '@/types'

const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const list = ref<TeamAdminSummary[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()

const keyword = ref('')
const status = ref<'all' | 'active' | 'disbanded'>('all')

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await adminListTeams({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      status: status.value === 'all' ? undefined : status.value,
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

function onSearch(): void {
  resetPage()
  void load()
}

// ---------------- 指派组织（存量团队迁移） ----------------
const orgs = ref<OrgDetail[]>([])
const assignOpen = ref(false)
const assignTeam = ref<TeamAdminSummary | null>(null)
const assignOrgId = ref('')
const assigning = ref(false)

async function loadOrgs(): Promise<void> {
  try {
    const result = await adminListOrgs({ page: 1, page_size: 100, status: 'active' })
    orgs.value = result.items
  } catch {
    /* 组织列表加载失败不阻塞团队列表 */
  }
}

function openAssign(row: TeamAdminSummary): void {
  assignTeam.value = row
  assignOrgId.value = row.org_id ?? ''
  assignOpen.value = true
}

async function submitAssign(): Promise<void> {
  if (!assignTeam.value || !assignOrgId.value) {
    message.warning(t('admin.teams.assignOrgRequired'))
    return
  }
  assigning.value = true
  try {
    await adminAssignTeamOrg(assignTeam.value.id, assignOrgId.value)
    message.success(t('admin.teams.assignOrgSuccess'))
    assignOpen.value = false
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    assigning.value = false
  }
}


// ---------------- 解散团队 ----------------
async function onDisband(row: TeamAdminSummary): Promise<void> {
  const ok = await confirmDialog({
    title: t('admin.teams.disbandTitle'),
    content: t('admin.teams.disbandConfirm'),
    positiveText: t('admin.teams.disband'),
    negativeText: t('action.cancel'),
    danger: true,
  })
  if (!ok) return
  try {
    await adminDisbandTeam(row.id)
    message.success(t('admin.teams.disbandSuccess'))
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  }
}

function actionsFor(row: TeamAdminSummary): RowAction[] {
  const actions: RowAction[] = [{ key: 'assignOrg', label: t('admin.teams.assignOrg') }]
  if (row.status === 'active') {
    actions.push({ key: 'disband', label: t('admin.teams.disband'), destructive: true })
  }
  return actions
}

function onRowAction(row: TeamAdminSummary, key: string): void {
  if (key === 'disband') {
    void onDisband(row)
    return
  }
  openAssign(row)
}


const columns = computed<AppTableColumn<TeamAdminSummary>[]>(() => [
  {
    key: 'avatar_url',
    title: t('admin.teams.avatar'),
    width: '64px',
    align: 'center',
    cell: (row) => h(BaseAvatar, { src: row.avatar_url, name: row.name, size: 36, kind: 'team' }),
  },
  {
    key: 'name',
    title: t('admin.teams.team'),
    cell: (row) => h('span', { class: 'font-medium' }, row.name),
  },
  {
    key: 'creator_nickname',
    title: t('admin.teams.creator'),
    width: '140px',
    cell: (row) => row.creator_nickname ?? '—',
  },
  {
    key: 'member_count',
    title: t('admin.teams.memberCount'),
    width: '80px',
    align: 'center',
    cell: (row) => String(row.member_count),
    cellClass: 'tabular-nums',
  },
  {
    key: 'problem_count',
    title: t('admin.teams.statProblems'),
    width: '90px',
    align: 'center',
    cell: (row) => String(row.problem_count),
    cellClass: 'tabular-nums text-muted-foreground',
  },
  {
    key: 'problem_set_count',
    title: t('admin.teams.statSets'),
    width: '70px',
    align: 'center',
    cell: (row) => String(row.problem_set_count),
    cellClass: 'tabular-nums text-muted-foreground',
  },
  {
    key: 'contest_count',
    title: t('admin.teams.statContests'),
    width: '70px',
    align: 'center',
    cell: (row) => String(row.contest_count),
    cellClass: 'tabular-nums text-muted-foreground',
  },
  {
    key: 'status',
    title: t('admin.teams.status'),
    width: '96px',
    cell: (row) =>
      h(ToneBadge, {
        tone: row.status === 'active' ? 'success' : 'danger',
        label: t(
          row.status === 'active' ? 'admin.teams.statusActive' : 'admin.teams.statusDisbanded',
        ),
      }),
  },
  {
    key: 'created_at',
    title: t('admin.teams.createdAt'),
    width: '160px',
    cell: (row) => formatDateTime(row.created_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
  {
    key: 'ops',
    width: '56px',
    align: 'right',
    cellClass: 'overflow-visible text-clip px-1',
    cell: (row) =>
      h(RowActions, {
        actions: actionsFor(row),
        label: t('action.more'),
        onSelect: (key: string) => onRowAction(row, key),
      }),
  },
])

onMounted(() => {
  void load()
  void loadOrgs()
})
</script>

<template>
  <WorkbenchShell :title="t('nav.teamsManage')">
    <template #toolbar>
      <SearchFilterBar
        :keyword="keyword"
        :placeholder="t('admin.teams.search')"
        @update:keyword="keyword = $event"
        @search="onSearch"
        @reset="onSearch"
      >
        <Select
          :model-value="status"
          @update:model-value="
            (value) => {
              status = String(value) as 'all' | 'active' | 'disbanded'
              onSearch()
            }
          "
        >
          <SelectTrigger class="h-9 w-[130px] text-[13px]">
            <SelectValue :placeholder="t('admin.teams.status')" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{{ t('common.allStatus') }}</SelectItem>
            <SelectItem value="active">{{ t('admin.teams.statusActive') }}</SelectItem>
            <SelectItem value="disbanded">{{ t('admin.teams.statusDisbanded') }}</SelectItem>
          </SelectContent>
        </Select>
        <template #actions>
          <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
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
      :empty-text="t('admin.teams.empty')"
      :row-click="(row) => router.push(`/admin/teams/${row.id}`)"
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
        <span class="tabular-nums">{{ t('admin.teams.totalCount', { count: total }) }}</span>
      </template>
    </PaginatedTable>

    <Dialog v-model:open="assignOpen">
      <DialogContent class="sm:max-w-[440px]">
        <DialogHeader>
          <DialogTitle>{{ t('admin.teams.assignOrgTitle') }}</DialogTitle>
          <DialogDescription>{{ t('admin.teams.assignOrgHint') }}</DialogDescription>
        </DialogHeader>
        <Select v-model="assignOrgId">
          <SelectTrigger class="h-9 w-full text-[13px]">
            <SelectValue :placeholder="t('admin.teams.assignOrgRequired')" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem v-for="org in orgs" :key="org.id" :value="org.id">
              {{ org.name }}
            </SelectItem>
          </SelectContent>
        </Select>
        <DialogFooter>
          <Button variant="outline" size="sm" :disabled="assigning" @click="assignOpen = false">
            {{ t('action.cancel') }}
          </Button>
          <Button size="sm" :disabled="assigning" @click="submitAssign">
            {{ t('admin.teams.assignOrg') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </WorkbenchShell>
</template>
