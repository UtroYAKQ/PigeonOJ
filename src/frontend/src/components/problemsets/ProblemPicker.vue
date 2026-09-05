<script setup lang="ts">
/**
 * 题库选择器弹窗（编排 / 挑题共用）：小型题库工作台。
 * 搜索 + 「我的」勾选（私有已发布）+ 分页；点「添加」即抛 add 事件，由宿主负责落库。
 */
import { computed, h, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { NButton } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { Search } from '@element-plus/icons-vue'

import { listProblems } from '@/api/problems'
import { usePagination } from '@/composables/usePagination'
import { useUserStore } from '@/stores/user'
import type { ProblemSummary } from '@/types'

const props = defineProps<{
  show: boolean
  /** 已选题目 id：用于去重与「已添加」禁用态 */
  chosenIds?: Set<string>
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  add: [problem: ProblemSummary]
}>()

const { t } = useI18n()
const userStore = useUserStore()

const keyword = ref('')
const mineOnly = ref(false)
const items = ref<ProblemSummary[]>([])
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

/** 竞态防护：慢响应不得覆盖新一次搜索结果 */
let seq = 0

async function load() {
  const s = ++seq
  const guard = beginLoad()
  try {
    const result = await listProblems({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      mine: mineOnly.value,
    })
    if (s !== seq || !isCurrent(guard)) return
    items.value = result.items
    total.value = result.total
  } catch {
    if (s !== seq || !isCurrent(guard)) return
    items.value = []
    total.value = 0
  }
}

const isManager = computed(() => userStore.isAdmin || userStore.hasAnyRole(['tutor']))

watch(
  () => props.show,
  (show) => {
    if (!show) return
    keyword.value = ''
    mineOnly.value = false
    resetPage()
    void load()
  },
)

function onSearch() {
  resetPage()
  void load()
}

function toggleMine(checked: boolean) {
  mineOnly.value = checked
  onSearch()
}

function onPage(p: number) {
  changePage(p)
  void load()
}

function rowKey(row: ProblemSummary) {
  return row.id
}

const columns = computed<DataTableColumns<ProblemSummary>>(() => [
  {
    title: t('problemSets.list.titleLabel'),
    key: 'title',
    minWidth: 200,
    render(row) {
      return h('div', { class: 'picker-name' }, [
        h('strong', null, row.title),
        h('span', null, `#${(row.id || '').slice(0, 8)}`),
      ])
    },
  },
  {
    title: t('problems.list.difficulty'),
    key: 'difficulty',
    width: 80,
    render: (row) => ((row.difficulty ?? null) === null ? '--' : String(row.difficulty)),
  },
  {
    title: t('problems.list.limits'),
    key: 'limits',
    width: 150,
    render: (row) => `${row.time_limit_ms} ms / ${row.memory_limit_mb} MB`,
  },
  {
    title: '',
    key: 'actions',
    width: 72,
    render(row) {
      const chosen = props.chosenIds?.has(row.id) ?? false
      return h(
        NButton,
        {
          size: 'tiny',
          secondary: true,
          type: chosen ? 'default' : 'primary',
          disabled: chosen,
          onClick: () => emit('add', row),
        },
        { default: () => (chosen ? t('problemSets.form.added') : t('problemSets.detail.add')) },
      )
    },
  },
])
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    style="width: min(780px, 94vw)"
    :title="t('problemSets.picker.title')"
    @update:show="emit('update:show', $event)"
  >
    <div class="picker">
      <div class="picker-toolbar">
        <n-input
          v-model:value="keyword"
          clearable
          :placeholder="t('problemSets.detail.pickProblem')"
          @keyup.enter="onSearch"
          @clear="onSearch"
        >
          <template #prefix>
            <n-icon :component="Search" />
          </template>
        </n-input>
        <n-button size="small" secondary @click="onSearch">
          {{ t('action.search') }}
        </n-button>
        <n-checkbox v-if="isManager" :checked="mineOnly" @update:checked="toggleMine">
          {{ t('problems.list.mineOnly') }}
        </n-checkbox>
      </div>

      <n-data-table
        size="small"
        :columns="columns"
        :data="items"
        :bordered="false"
        :bottom-bordered="false"
        :row-key="rowKey"
        :empty="t('problemSets.detail.noResult')"
        class="picker-table"
      />
      <div class="picker-pager">
        <n-pagination
          size="small"
          :page="page"
          :page-size="pageSize"
          :item-count="total"
          @update:page="onPage"
        />
      </div>
    </div>
  </n-modal>
</template>

<style scoped>
.picker {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.picker-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
}
.picker-toolbar :deep(.n-input) {
  max-width: 320px;
}
.picker-table {
  min-height: 220px;
}
.picker-pager {
  display: flex;
  justify-content: flex-end;
}
.picker-name {
  display: grid;
  gap: 2px;
}
.picker-name strong {
  font-size: 13px;
}
.picker-name span {
  color: var(--app-text-secondary);
  font-size: 12px;
}
</style>
