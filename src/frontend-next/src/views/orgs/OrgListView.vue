<script setup lang="ts">
import { onActivated, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { listMyOrgs } from '@/api/orgs'
import PaginatedCardGrid from '@/components/common/PaginatedCardGrid.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import WorkbenchShell from '@/components/common/WorkbenchShell.vue'
import OrgCard from '@/components/orgs/OrgCard.vue'
import { usePagination } from '@/composables/usePagination'
import { message } from '@/utils/feedback'
import type { OrgSummary } from '@/types'

const router = useRouter()
const { t } = useI18n()

const orgs = ref<OrgSummary[]>([])
const loading = ref(false)
const keyword = ref('')
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

async function load(): Promise<void> {
  const seq = beginLoad()
  loading.value = true
  try {
    const result = await listMyOrgs({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
    })
    if (!isCurrent(seq)) return
    orgs.value = result.items
    total.value = result.total
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('orgs.list.loadFailed'))
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

function openOrg(org: OrgSummary): void {
  void router.push(`/orgs/${org.id}`)
}

onMounted(load)

// 组织归属可能在别处变化（管理端创建 / 加入），缓存页重新激活时刷新
let activatedOnce = false
onActivated(() => {
  if (activatedOnce) void load()
  else activatedOnce = true
})
</script>

<template>
  <WorkbenchShell :title="t('nav.orgs')">
    <template #toolbar>
      <SearchFilterBar
        :keyword="keyword"
        :placeholder="t('orgs.list.search')"
        @update:keyword="keyword = $event"
        @search="onSearch"
        @reset="onSearch"
      >
        <template #actions>
          <RefreshButton :loading="loading" :label="t('action.refresh')" @click="load" />
        </template>
      </SearchFilterBar>
    </template>

    <PaginatedCardGrid
      :items="orgs"
      :loading="loading"
      :total="total"
      :page="page"
      :page-size="pageSize"
      :empty-text="t('orgs.list.empty')"
      @update:page="onPageChange"
    >
      <template #default="{ item }">
        <OrgCard :org="item" @open="openOrg" />
      </template>
      <template #pager-left>
        <span class="tabular-nums">{{ t('orgs.list.totalCount', { count: total }) }}</span>
      </template>
    </PaginatedCardGrid>
  </WorkbenchShell>
</template>
