<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Plus } from '@lucide/vue'

import { listTeamContests } from '@/api/teams'
import PaginatedCardGrid from '@/components/common/PaginatedCardGrid.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import ContestCard from '@/components/contests/ContestCard.vue'
import RowActions from '@/components/teams/RowActions.vue'
import type { RowAction } from '@/components/teams/types'
import { Button } from '@/components/ui/button'
import { usePagination } from '@/composables/usePagination'
import { message } from '@/utils/feedback'
import type { ContestSummary } from '@/types'

type ContestAction = 'manage' | 'tools'

const props = defineProps<{
  teamId: string
  isAdmin: boolean
}>()

const router = useRouter()
const { t } = useI18n()

const contests = ref<ContestSummary[]>([])
const loading = ref(false)
const keyword = ref('')
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await listTeamContests(props.teamId, {
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
    })
    if (!isCurrent(seq)) return
    contests.value = result.items
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

function onPageChange(value: number): void {
  changePage(value)
  void load()
}

function openContest(row: ContestSummary): void {
  // 限界上下文：留在团队路由前缀内
  void router.push(`/teams/${props.teamId}/contests/${row.id}`)
}

function openCreate(): void {
  void router.push(`/teams/${props.teamId}/contests/new`)
}

function actionsFor(row: ContestSummary): RowAction[] {
  return [
    {
      key: 'manage',
      label: t('contests.detail.manage'),
      disabled: row.status !== 'scheduled',
    },
    { key: 'tools', label: t('contests.tools.title') },
  ]
}

function onAction(key: ContestAction, row: ContestSummary): void {
  if (key === 'manage') {
    if (row.status !== 'scheduled') return
    void router.push(`/teams/${props.teamId}/contests/${row.id}/edit/basic`)
    return
  }
  void router.push(`/teams/${props.teamId}/contests/${row.id}/tools`)
}

onMounted(load)
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col gap-3">
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('contests.list.search')"
      @update:keyword="keyword = $event"
      @search="onSearch"
      @reset="onSearch"
    >
      <template #actions>
        <Button v-if="isAdmin" size="toolbar" @click="openCreate">
          <Plus class="size-4" />
          {{ t('teams.space.createContest') }}
        </Button>
        <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
      </template>
    </SearchFilterBar>

    <PaginatedCardGrid
      :items="contests"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :empty-text="t('teams.space.contestsEmpty')"
      @update:page="onPageChange"
    >
      <template #default="{ item }">
        <div class="relative h-full">
          <ContestCard :contest="item" @open="openContest" />
          <div v-if="isAdmin" class="absolute bottom-1.5 right-1.5">
            <RowActions
              :actions="actionsFor(item)"
              :label="t('teams.detail.more')"
              @select="(key) => onAction(key as ContestAction, item)"
            />
          </div>
        </div>
      </template>
      <template #pager-left>
        <span class="tabular-nums">{{ t('teams.pane.contestTotal', { count: total }) }}</span>
      </template>
    </PaginatedCardGrid>
  </div>
</template>