<script setup lang="ts">
/**
 * 题库选择器弹窗（题单编排 / 团队引用共用）：小型题库工作台。
 * 搜索 + 管理角色「我的」勾选（私有已发布）+ 分页；点「添加」抛 add 事件，由宿主负责落库。
 *
 * 对外契约（与旧工程保持一致，其他模块直接复用，勿改名）：
 * - props: show / chosenIds? / defaultMine? / loader?
 * - emits: update:show / add
 */
import { computed, h, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { listProblems } from '@/api/problems'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { Switch } from '@/components/ui/switch'
import { usePagination } from '@/composables/usePagination'
import { useUserStore } from '@/stores/user'
import type { PageResult, ProblemSummary } from '@/types'

const props = defineProps<{
  show: boolean
  /** 已选题目 id：用于去重与「已添加」禁用态 */
  chosenIds?: Set<string>
  /** 进入时默认勾选「我的」（团队引用等场景：仅本人题目可被引用） */
  defaultMine?: boolean
  /** 自定义候选源（团队编排走 arrangeable）；缺省为全站题库 */
  loader?: (query: {
    page: number
    page_size: number
    keyword?: string
    mine?: boolean
  }) => Promise<PageResult<ProblemSummary>>
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  add: [problem: ProblemSummary]
}>()

const { t } = useI18n()
const userStore = useUserStore()

const keyword = ref('')
const mineOnly = ref(props.defaultMine ?? false)
const items = ref<ProblemSummary[]>([])
const loading = ref(false)
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()

/** 竞态防护：慢响应不得覆盖新一次搜索结果 */
let seq = 0

async function load(): Promise<void> {
  const current = ++seq
  const guard = beginLoad()
  loading.value = true
  try {
    const query = {
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      mine: mineOnly.value,
    }
    const result = await (props.loader ? props.loader(query) : listProblems(query))
    if (current !== seq || !isCurrent(guard)) return
    items.value = result.items
    total.value = result.total
  } catch {
    if (current !== seq || !isCurrent(guard)) return
    items.value = []
    total.value = 0
  } finally {
    if (current === seq && isCurrent(guard)) loading.value = false
  }
}

const isManager = computed(() => userStore.isAdmin)

watch(
  () => props.show,
  (show) => {
    if (!show) return
    keyword.value = ''
    mineOnly.value = props.defaultMine ?? false
    resetPage()
    void load()
  },
  { immediate: true },
)

function onSearch(): void {
  resetPage()
  void load()
}

function toggleMine(value: boolean): void {
  mineOnly.value = value
  onSearch()
}

function onPage(value: number): void {
  changePage(value)
  void load()
}

function onPageSize(value: number): void {
  changeSize(value)
  void load()
}

const columns = computed<AppTableColumn<ProblemSummary>[]>(() => [
  {
    key: 'title',
    title: t('problemSets.list.titleLabel'),
    cell: (row) =>
      h('div', { class: 'grid gap-0.5 py-0.5' }, [
        h('span', { class: 'font-medium text-[13px]' }, row.title),
        h(
          'span',
          { class: 'font-mono text-[11px] text-muted-foreground' },
          `#${(row.id || '').slice(0, 8)}`,
        ),
      ]),
  },
  {
    key: 'difficulty',
    title: t('problems.list.difficulty'),
    width: '80px',
    align: 'center',
    cell: (row) => ((row.difficulty ?? null) === null ? '--' : String(row.difficulty)),
    cellClass: 'tabular-nums text-muted-foreground',
  },
  {
    key: 'limits',
    title: t('problems.list.limits'),
    width: '150px',
    cell: (row) => `${row.time_limit_ms} ms / ${row.memory_limit_mb} MB`,
    cellClass: 'text-[12.5px] text-muted-foreground tabular-nums',
  },
  {
    key: 'actions',
    width: '84px',
    align: 'right',
    cell: (row) => {
      const chosen = props.chosenIds?.has(row.id) ?? false
      return h(
        Button,
        {
          size: 'xs',
          variant: chosen ? 'outline' : 'default',
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
  <Dialog :open="show" @update:open="emit('update:show', $event)">
    <DialogContent
      class="flex h-[86vh] max-h-[640px] w-[94vw] max-w-[860px] flex-col gap-0 overflow-hidden p-0 sm:max-w-[860px]"
    >
      <header class="shrink-0 border-b border-border px-5 py-3.5 pr-12">
        <DialogTitle class="text-[15px] font-semibold">{{
          t('problemSets.picker.title')
        }}</DialogTitle>
        <DialogDescription class="sr-only">{{ t('problemSets.picker.title') }}</DialogDescription>
      </header>

      <div class="flex min-h-0 flex-1 flex-col gap-3 p-4">
        <SearchFilterBar
          :keyword="keyword"
          :placeholder="t('problemSets.detail.pickProblem')"
          search-width="300px"
          @update:keyword="keyword = $event"
          @search="onSearch"
          @reset="onSearch"
        >
          <div v-if="isManager && !loader" class="flex items-center gap-2">
            <Switch
              id="problem-picker-mine"
              :model-value="mineOnly"
              :aria-label="t('problems.list.mineOnly')"
              class="scale-90"
              @update:model-value="toggleMine"
            />
            <label for="problem-picker-mine" class="text-[13px] text-muted-foreground">
              {{ t('problems.list.mineOnly') }}
            </label>
          </div>
        </SearchFilterBar>

        <PaginatedTable
          :columns="columns"
          :data="items"
          :loading="loading"
          :total="total"
          :page="page"
          :page-size="pageSize"
          :empty-text="t('problemSets.detail.noResult')"
          class="min-h-0 flex-1"
          @update:page="onPage"
          @update:page-size="onPageSize"
        >
          <template #pager-left>
            <span class="tabular-nums">{{
              t('problemSets.list.totalCount', { count: total })
            }}</span>
          </template>
        </PaginatedTable>
      </div>
    </DialogContent>
  </Dialog>
</template>
