<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { DataTableColumns } from 'naive-ui'

import { listActiveTags, listProblems } from '@/api/problems'
import { message } from '@/utils/feedback'
import { usePagination } from '@/composables/usePagination'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import type { PageResult, ProblemSummary, ProblemTagItem } from '@/types'

const router = useRouter()
const { t } = useI18n()
const loading = ref(false)
const problems = ref<ProblemSummary[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage } = usePagination()
const keyword = ref('')
/** 标签筛选（单选） */
const tag = ref<string | null>(null)
const tagOptions = ref<Array<{ label: string; value: string }>>([])

async function load() {
  loading.value = true
  try {
    const result: PageResult<ProblemSummary> = await listProblems({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      tag: tag.value || undefined,
    })
    problems.value = result.items
    total.value = result.total
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.list.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function loadTagOptions() {
  try {
    const tags: ProblemTagItem[] = await listActiveTags()
    tagOptions.value = tags.map((item) => ({ label: item.name, value: item.name }))
  } catch {
    /* 标签加载失败不阻塞列表 */
  }
}

/** 搜索 / 清空筛选：SearchFilterBar 内部已做输入防抖，这里立即查询 */
function onSearch() {
  resetPage()
  load()
}

function changeTag() {
  resetPage()
  load()
}

onMounted(() => {
  load()
  loadTagOptions()
})

const columns = computed<DataTableColumns<ProblemSummary>>(() => [
  {
    title: t('problems.list.name'),
    key: 'title',
    minWidth: 280,
    render(row) {
      return h('div', { class: 'problem-name' }, [
        h('strong', null, row.title),
        h('span', null, `#${(row.id || '').slice(0, 8)}`),
      ])
    },
  },
  {
    title: t('problems.list.limits'),
    key: 'limits',
    width: 220,
    render: (row) => `${row.time_limit_ms} ms / ${row.memory_limit_mb} MB`,
  },
])

function rowProps(row: ProblemSummary) {
  return {
    style: 'cursor: pointer;',
    onClick: () => router.push(`/problems/${row.id}`),
  }
}
</script>

<template>
  <!-- 题库中心：内容自适应高度，不做视口填充（其余列表工作台仍用 page-fill） -->
  <div class="page-stack">
    <n-card :bordered="false">
      <SearchFilterBar
        :keyword="keyword"
        :placeholder="t('problems.list.search')"
        search-width="300px"
        @update:keyword="(v: string) => { keyword = v }"
        @search="onSearch"
        @reset="onSearch"
      >
        <n-select
          v-model:value="tag"
          style="width: 150px"
          clearable
          :options="tagOptions"
          :placeholder="t('problems.list.tag')"
          @update:value="changeTag"
        />
        <template #actions>
          <n-button quaternary circle :loading="loading" :aria-label="t('action.refresh')" @click="load">
            <n-icon :component="Refresh" />
          </n-button>
        </template>
      </SearchFilterBar>

      <!-- 表格区撑满卡片剩余高度；无数据时空态垂直居中 -->
      <PaginatedDataTable
        :columns="columns"
        :data="problems"
        :loading="loading"
        :total="total"
        v-model:page="page"
        v-model:page-size="pageSize"
        :page-sizes="[20, 50, 100]"
        :empty-text="t('problems.list.empty')"
        :table-props="{ rowProps }"
        @update:page="(p: number) => { changePage(p); load() }"
        @update:page-size="(s: number) => { changeSize(s); load() }"
      >
        <template #pager-left>
          <span class="pager__total">{{ t('problems.list.totalCount', { count: total }) }}</span>
        </template>
      </PaginatedDataTable>
    </n-card>
  </div>
</template>

<style scoped>
.problem-name {
  display: grid;
  gap: 4px;
}
.problem-name strong {
  font-size: 14px;
}
.problem-name span {
  color: var(--app-text-secondary);
  font-size: 12px;
}
</style>
