<script setup lang="ts">
import { computed, h, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import type { VNode } from 'vue'

import { adminListTeamMembers } from '@/api/admin'
import BaseAvatar from '@/components/common/BaseAvatar.vue'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import TeamRoleBadge from '@/components/teams/TeamRoleBadge.vue'
import { formatDateTime } from '@/utils/format'
import { useTeamModuleList } from './useTeamModuleList'
import type { TeamMemberItem, TeamRoleType } from '@/types'

const props = defineProps<{ teamId: string }>()

const { t } = useI18n()
const { loading, rows, keyword, page, pageSize, total, load, onSearch, onPage, onPageSize } =
  useTeamModuleList<TeamMemberItem>((query) => adminListTeamMembers(props.teamId, query))

function roleCell(row: TeamMemberItem): VNode {
  const role: TeamRoleType = row.is_creator ? 'creator' : row.is_admin ? 'admin' : 'member'
  return h(TeamRoleBadge, { role })
}

const columns = computed<AppTableColumn<TeamMemberItem>[]>(() => [
  {
    key: 'avatar_url',
    title: t('admin.teams.avatar'),
    width: '64px',
    align: 'center',
    cell: (row) => h(BaseAvatar, { src: row.avatar_url, name: row.nickname, size: 36 }),
  },
  {
    key: 'nickname',
    title: t('teams.members.user'),
    cell: (row) => h('span', { class: 'font-medium' }, row.nickname),
  },
  {
    key: 'role',
    title: t('teams.members.role'),
    width: '110px',
    cell: roleCell,
  },
  {
    key: 'joined_at',
    title: t('admin.teams.memberJoinedAt'),
    width: '160px',
    cell: (row) => formatDateTime(row.joined_at),
    cellClass: 'text-[12.5px] text-muted-foreground',
  },
  {
    key: 'note',
    title: t('teams.members.note'),
    cell: (row) => h('span', { class: 'text-[12.5px] text-muted-foreground' }, row.note ?? '—'),
  },
])

onMounted(load)
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col gap-2.5">
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('teams.members.search')"
      @update:keyword="keyword = $event"
      @search="onSearch"
      @reset="onSearch"
    >
      <template #actions>
        <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
      </template>
    </SearchFilterBar>

    <PaginatedTable
      :columns="columns"
      :data="rows"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :page-sizes="[10, 20, 50]"
      show-size-picker
      :empty-text="t('admin.teams.membersEmpty')"
      @update:page="onPage"
      @update:page-size="onPageSize"
    >
      <template #pager-left>
        <span class="tabular-nums">{{ t('teams.pane.memberTotal', { count: total }) }}</span>
      </template>
    </PaginatedTable>
  </div>
</template>
