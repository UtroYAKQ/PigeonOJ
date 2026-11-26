<script setup lang="ts">
/**
 * 团队中心（/teams/mine）：默认公开团队列表（可申请加入）；
 * 「我的团队」切换为在册团队（公开 + 私有，含我的角色）。
 * 退出 / 解散团队后经 stores/teams 脏标记在 onActivated 时重拉，避免角色标签过期。
 */
import { onActivated, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { listMyTeams, listTeams } from '@/api/teams'
import FilterCheckbox from '@/components/common/FilterCheckbox.vue'
import PaginatedCardGrid from '@/components/common/PaginatedCardGrid.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import TeamCard from '@/components/teams/TeamCard.vue'
import { usePagination } from '@/composables/usePagination'
import { useTeamsStore } from '@/stores/teams'
import { message } from '@/utils/feedback'
import type { TeamSummary } from '@/types'
import JoinTeamDialog from './components/JoinTeamDialog.vue'

const router = useRouter()
const { t } = useI18n()

const teams = ref<TeamSummary[]>([])
const loading = ref(false)
const keyword = ref('')
const mineOnly = ref(false)
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

/** 申请本地态：已申请集合防重复点击（重复申请由后端 3003 兜底） */
const appliedIds = ref(new Set<string>())
const joinOpen = ref(false)
const joinTarget = ref<TeamSummary | null>(null)

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const query = {
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
    }
    const result = mineOnly.value ? await listMyTeams(query) : await listTeams(query)
    if (!isCurrent(seq)) return
    teams.value = result.items
    total.value = result.total
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('teams.list.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}

function onSearch(): void {
  resetPage()
  void load()
}

function onToggleMine(value: boolean): void {
  mineOnly.value = value
  onSearch()
}

function onPageChange(value: number): void {
  changePage(value)
  void load()
}

function openTeam(row: TeamSummary): void {
  if (row.my_role) {
    void router.push(`/teams/${row.id}`)
    return
  }
  if (mineOnly.value) return
  if (appliedIds.value.has(row.id)) {
    message.info(t('teams.list.appliedHint'))
    return
  }
  openJoin(row)
}

function openJoin(row: TeamSummary): void {
  joinTarget.value = row
  joinOpen.value = true
}

function onApplied(teamId: string): void {
  appliedIds.value.add(teamId)
}

onMounted(load)

// keepAlive 缓存页：退出 / 解散后回退本页时（脏标记）重拉
onActivated(() => {
  if (useTeamsStore().consumeMembershipDirty()) void load()
})
</script>

<template>
  <WorkbenchShell :title="t('nav.teams')">
    <template #toolbar>
      <SearchFilterBar
        :keyword="keyword"
        :placeholder="t('teams.list.search')"
        search-width="300px"
        @update:keyword="keyword = $event"
        @search="onSearch"
        @reset="onSearch"
      >
        <template #actions>
          <FilterCheckbox
            id="team-list-mine"
            :model-value="mineOnly"
            :label="t('teams.list.myTeams')"
            @update:model-value="onToggleMine"
          />
          <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
        </template>
      </SearchFilterBar>
    </template>

    <PaginatedCardGrid
      :items="teams"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :empty-text="t(mineOnly ? 'teams.list.empty' : 'teams.list.emptyPublic')"
      @update:page="onPageChange"
    >
      <template #default="{ item }">
        <TeamCard
          :team="item"
          :mine-only="mineOnly"
          :applied="appliedIds.has(item.id)"
          @open="openTeam"
        />
      </template>
      <template #pager-left>
        <span class="tabular-nums">{{ t('teams.list.totalCount', { count: total }) }}</span>
      </template>
    </PaginatedCardGrid>

    <JoinTeamDialog v-model:open="joinOpen" :team="joinTarget" @applied="onApplied" />
  </WorkbenchShell>
</template>
