<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Plus } from '@lucide/vue'

import { listOrgTeams } from '@/api/orgs'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ToneBadge from '@/components/common/ToneBadge.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import CreateTeamDialog from '@/components/teams/CreateTeamDialog.vue'
import TeamRoleBadge from '@/components/teams/TeamRoleBadge.vue'
import { Button } from '@/components/ui/button'
import { usePagination } from '@/composables/usePagination'
import { message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { TeamSummary } from '@/types'

const props = withDefaults(
  defineProps<{ orgId: string; canManage: boolean; adminMode?: boolean }>(),
  { adminMode: false },
)

const router = useRouter()
const { t } = useI18n()

const teams = ref<TeamSummary[]>([])
const loading = ref(false)
const keyword = ref('')
const createOpen = ref(false)
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await listOrgTeams(props.orgId, {
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
    })
    if (!isCurrent(seq)) return
    teams.value = result.items
    total.value = result.total
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('orgs.detail.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

function onSearch(): void {
  resetPage()
  void load()
}

function onPageChange(value: number): void {
  changePage(value)
  void load()
}

function onCreated(team: TeamSummary): void {
  message.success(t('orgs.teams.created'))
  createOpen.value = false
  void load()
  void router.push(`/teams/${team.id}`)
}

const columns = computed<AppTableColumn<TeamSummary>[]>(() => [
  {
    key: 'name',
    title: t('teams.list.name'),
    cell: (row) =>
      h('div', { class: 'flex min-w-0 items-center gap-2.5 py-0.5' }, [
        h(BaseAvatar, { src: row.avatar_url, name: row.name, size: 30, round: false, radius: 8 }),
        h('span', { class: 'truncate font-medium', title: row.name }, row.name),
        row.visibility === 'private'
          ? h(ToneBadge, { tone: 'danger', label: t('teams.settings.visibilityPrivate') })
          : null,
      ]),
  },
  {
    key: 'member_count',
    title: t('orgs.list.memberCount'),
    width: '90px',
    align: 'right',
    cell: (row) => String(row.member_count),
    cellClass: 'tabular-nums text-muted-foreground',
  },
  {
    key: 'my_role',
    title: t('teams.members.role'),
    width: '110px',
    cell: (row) => (row.my_role ? h(TeamRoleBadge, { role: row.my_role }) : '—'),
  },
  {
    key: 'created_at',
    title: t('orgs.list.createdAt'),
    width: '160px',
    cell: (row) => formatDateTime(row.created_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
])

onMounted(load)
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col gap-3">
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('orgs.teams.search')"
      @update:keyword="keyword = $event"
      @search="onSearch"
      @reset="onSearch"
    >
      <template #actions>
        <Button v-if="canManage" variant="outline" size="toolbar" @click="createOpen = true">
          <Plus class="size-4" />
          {{ t('orgs.teams.create') }}
        </Button>
        <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
      </template>
    </SearchFilterBar>

    <PaginatedTable
      :columns="columns"
      :data="teams"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      show-size-picker
      :empty-text="t('orgs.teams.empty')"
      :row-click="
        (row) => router.push(props.adminMode ? `/admin/teams/${row.id}` : `/teams/${row.id}`)
      "
      @update:page="onPageChange"
    />

    <CreateTeamDialog v-model:open="createOpen" :org-id="orgId" @created="onCreated" />
  </div>
</template>