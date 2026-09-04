<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import RefreshButton from '@/components/RefreshButton.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { listProblemSets } from '@/api/problemSets'
import { message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import { useUserStore } from '@/stores/user'
import type { PageResult, ProblemSetSummary } from '@/types'

const router = useRouter()
const { t } = useI18n()
const loading = ref(false)
const sets = ref<ProblemSetSummary[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()
const keyword = ref('')
/** 「我的」勾选仅对题单管理角色（admin/tutor）开放：只看本人未下线题单（含私有） */
const userStore = useUserStore()
const isManager = computed(() => userStore.isAdmin || userStore.hasAnyRole(['tutor']))
const mineOnly = ref(false)

async function load() {
  const seq = beginLoad()
  loading.value = true
  try {
    const result: PageResult<ProblemSetSummary> = await listProblemSets({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      mine: mineOnly.value,
    })
    if (!isCurrent(seq)) return
    sets.value = result.items
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

const columns = computed<DataTableColumns<ProblemSetSummary>>(() => [
  {
    title: t('problemSets.list.titleLabel'),
    key: 'title',
    minWidth: 280,
    render(row) {
      return h('div', { class: 'set-name__row' }, [
        h('strong', null, row.title),
        row.visibility === 'private'
          ? h(NTag, { size: 'small', bordered: false, type: 'error' }, { default: () => t('problemSets.list.privateTag') })
          : null,
      ])
    },
  },
  {
    title: t('problemSets.detail.problems'),
    key: 'item_count',
    width: 120,
    render: (row) => t('problemSets.list.itemCount', { count: row.item_count }),
  },
])

function rowProps(row: ProblemSetSummary) {
  return {
    style: 'cursor: pointer;',
    onClick: () => router.push(`/problem-sets/${row.id}`),
  }
}
</script>

<template>
  <!-- 题单中心（浏览）：管理入口统一在管理后台 /admin/problem-sets -->
  <WorkbenchShell>
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('problemSets.list.search')"
      search-width="300px"
      manual
      @update:keyword="
        (v: string) => {
          keyword = v
        }
      "
      @search="onSearch"
      @reset="onSearch"
    >
      <template #actions>
        <n-checkbox v-if="isManager" v-model:checked="mineOnly" @update:checked="onSearch">
          {{ t('problemSets.list.mineOnly') }}
        </n-checkbox>
        <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
      </template>
    </SearchFilterBar>

    <PaginatedDataTable
      :columns="columns"
      :data="sets"
      :loading="loading"
      :total="total"
      v-model:page="page"
      v-model:page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      :empty-text="t('problemSets.list.empty')"
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
        <span class="pager__total">{{ t('problemSets.list.totalCount', { count: total }) }}</span>
      </template>
    </PaginatedDataTable>
  </WorkbenchShell>
</template>

<style scoped>
.set-name {
  display: grid;
  gap: 4px;
}
.set-name__row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.set-name strong {
  font-size: 14px;
}
.set-name span {
  color: var(--app-text-secondary);
  font-size: 12px;
}
</style>
