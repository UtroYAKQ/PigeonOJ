<script setup lang="ts">
import { Refresh, Search as SearchIcon } from '@element-plus/icons-vue'
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { DataTableColumns } from 'naive-ui'

import { listActiveTags, listProblems } from '@/api/problems'
import { message } from '@/utils/feedback'
import type { PageResult, ProblemSummary, ProblemTagItem } from '@/types'

const router = useRouter()
const { t } = useI18n()
const loading = ref(false)
const problems = ref<ProblemSummary[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
/** 标签筛选（单选；docs/decisions/2026-08-24-remove-difficulty-use-tags.md） */
const tag = ref<string | null>(null)
const tagOptions = ref<Array<{ label: string; value: string }>>([])
let searchTimer: number | undefined

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

function scheduleSearch() {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    page.value = 1
    load()
  }, 300)
}

// 中文输入法组词过程不触发搜索（compositionend 后再统一触发）
let composing = false
function onCompositionStart() {
  composing = true
}
function onCompositionEnd() {
  composing = false
  scheduleSearch()
}
function onKeywordInput() {
  if (!composing) scheduleSearch()
}
function onKeywordClear() {
  page.value = 1
  load()
}

function changeTag() {
  page.value = 1
  load()
}
function changePage(value: number) {
  page.value = value
  load()
}
function changeSize(value: number) {
  pageSize.value = value
  page.value = 1
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
      <div class="toolbar">
        <n-input
          v-model:value="keyword"
          clearable
          class="toolbar__search"
          :placeholder="t('problems.list.name')"
          @input="onKeywordInput"
          @compositionstart="onCompositionStart"
          @compositionend="onCompositionEnd"
          @clear="onKeywordClear"
        >
          <template #prefix>
            <n-icon size="15"><SearchIcon /></n-icon>
          </template>
        </n-input>
        <n-select
          v-model:value="tag"
          class="toolbar__tag"
          clearable
          :options="tagOptions"
          :placeholder="t('problems.list.tag')"
          @update:value="changeTag"
        />
        <div class="toolbar__actions">
          <n-button quaternary circle :loading="loading" :aria-label="t('action.refresh')" @click="load">
            <n-icon :component="Refresh" />
          </n-button>
        </div>
      </div>

      <!-- 表格区撑满卡片剩余高度；无数据时空态垂直居中 -->
      <n-data-table
        v-if="loading || problems.length"
        class="table-fill"
        :columns="columns"
        :data="problems"
        :loading="loading"
        :row-props="rowProps"
        :bordered="false"
        :bottom-bordered="false"
      />
      <div v-else class="table-fill-empty">
        <n-empty size="large" :description="t('problems.list.empty')" />
      </div>

      <div class="pager">
        <span class="pager__total">{{ t('problems.list.totalCount', { count: total }) }}</span>
        <n-pagination
          :page="page"
          :page-size="pageSize"
          :item-count="total"
          :page-sizes="[20, 50, 100]"
          show-size-picker
          @update:page="changePage"
          @update:page-size="changeSize"
        />
      </div>
    </n-card>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.toolbar__search {
  width: 300px;
}
.toolbar__tag {
  width: 150px;
}
.toolbar__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}
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
.pager {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--app-border);
}
.pager__total {
  color: var(--app-text-secondary);
  font-size: 13px;
}
@media (max-width: 600px) {
  .toolbar__search,
  .toolbar__tag {
    width: 100%;
  }
  .toolbar__actions {
    margin-left: 0;
  }
  .pager {
    justify-content: center;
  }
}
</style>
