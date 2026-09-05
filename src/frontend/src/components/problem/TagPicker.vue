<script setup lang="ts">
/**
 * 标签选择器弹窗：搜索 + 分页。
 * 与 ProblemPicker 同款交互：点「选择」即抛 select 事件，由宿主负责落库。
 */
import { computed, h, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { NButton, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { Search } from '@element-plus/icons-vue'

import { listActiveTagsPaged } from '@/api/problems'
import { usePagination } from '@/composables/usePagination'
import type { PageResult, ProblemTagItem } from '@/types'

const props = defineProps<{
  show: boolean
  /** 已选标签名：用于去重与「已添加」禁用态 */
  chosenNames?: Set<string>
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  select: [tag: ProblemTagItem]
}>()

const { t } = useI18n()

const keyword = ref('')
const items = ref<ProblemTagItem[]>([])
const { page, pageSize, total, changePage, resetPage, beginLoad, isCurrent } = usePagination()

/** 竞态防护：慢响应不得覆盖新一次搜索结果 */
let seq = 0

async function load() {
  const s = ++seq
  const guard = beginLoad()
  try {
    const result: PageResult<ProblemTagItem> = await listActiveTagsPaged({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
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

watch(
  () => props.show,
  (show) => {
    if (!show) return
    keyword.value = ''
    resetPage()
    void load()
  },
)

function onSearch() {
  resetPage()
  void load()
}

function onPage(p: number) {
  changePage(p)
  void load()
}

function rowKey(row: ProblemTagItem) {
  return row.id
}

const columns = computed<DataTableColumns<ProblemTagItem>>(() => [
  {
    title: t('problems.create.tags'),
    key: 'name',
    minWidth: 160,
    render(row) {
      return h(
        NTag,
        {
          size: 'small',
          bordered: false,
          color: row.color ? { color: row.color, textColor: '#fff' } : undefined,
        },
        { default: () => row.name },
      )
    },
  },
  {
    title: t('problems.create.tagColor'),
    key: 'color',
    width: 120,
    render(row) {
      if (!row.color) return '—'
      return h('span', { class: 'color-cell' }, [
        h('span', {
          class: 'color-dot',
          style: { backgroundColor: row.color },
        }),
        row.color,
      ])
    },
  },
  {
    title: '',
    key: 'actions',
    width: 80,
    render(row) {
      const chosen = props.chosenNames?.has(row.name) ?? false
      return h(
        NButton,
        {
          size: 'tiny',
          secondary: true,
          type: chosen ? 'default' : 'primary',
          disabled: chosen,
          onClick: () => emit('select', row),
        },
        { default: () => (chosen ? t('problemSets.form.added') : t('problems.create.selectTag')) },
      )
    },
  },
])
</script>

<template>
  <n-modal
    :show="show"
    preset="card"
    style="width: min(560px, 94vw)"
    :title="t('problems.create.selectTagTitle')"
    @update:show="emit('update:show', $event)"
  >
    <div class="tag-picker">
      <div class="tag-picker-toolbar">
        <n-input
          v-model:value="keyword"
          clearable
          :placeholder="t('problems.create.searchTagPlaceholder')"
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
      </div>

      <n-data-table
        size="small"
        :columns="columns"
        :data="items"
        :bordered="false"
        :bottom-bordered="false"
        :row-key="rowKey"
        class="tag-picker-table"
      />
      <n-empty
        v-if="!items.length"
        size="small"
        :description="t('problems.create.noTagsFound')"
        class="tag-picker-empty"
      />
      <div class="tag-picker-pager">
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
.tag-picker {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.tag-picker-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
}
.tag-picker-toolbar :deep(.n-input) {
  max-width: 320px;
}
.tag-picker-table {
  min-height: 220px;
}
.tag-picker-empty {
  padding: 12px 0;
}
.tag-picker-pager {
  display: flex;
  justify-content: flex-end;
}
.color-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}
.color-dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 3px;
}
</style>
