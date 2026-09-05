<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import RefreshButton from '@/components/RefreshButton.vue'
import { listActiveTags, listProblems } from '@/api/problems'
import { message } from '@/utils/feedback'
import { renderSolveMark } from '@/utils/solveMark'
import { useUserStore } from '@/stores/user'
import { usePagination } from '@/composables/usePagination'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import type { PageResult, ProblemSummary, ProblemTagItem } from '@/types'

const router = useRouter()
const { t } = useI18n()
const loading = ref(false)
const problems = ref<ProblemSummary[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()
const keyword = ref('')
/** 标签筛选（单选） */
const tag = ref<string | null>(null)
const tagOptions = ref<Array<{ label: string; value: string }>>([])
/** 难度分闭区间筛选（null = 不限） */
const difficultyMin = ref<number | null>(null)
const difficultyMax = ref<number | null>(null)
/** 「我的」勾选仅对题库管理角色（admin/tutor）开放：只看本人已发布题目（含私有已发布） */
const userStore = useUserStore()
const isManager = computed(() => userStore.isAdmin || userStore.hasAnyRole(['tutor']))
const mineOnly = ref(false)

async function load() {
  const seq = beginLoad()
  loading.value = true
  try {
    const result: PageResult<ProblemSummary> = await listProblems({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      tag: tag.value || undefined,
      mine: mineOnly.value,
      difficulty_min: difficultyMin.value ?? undefined,
      difficulty_max: difficultyMax.value ?? undefined,
    })
    if (!isCurrent(seq)) return
    problems.value = result.items
    total.value = result.total
  } catch (error) {
    if (!isCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('problems.list.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
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

/** 查询（手动模式：点击「查询」按钮 / 回车 / 清空关键字触发） */
function onSearch() {
  resetPage()
  load()
}

function changeTag() {
  resetPage()
  load()
}

/** 通过率展示：accepted/submission 百分比；无提交显示 -- */
function passRate(row: ProblemSummary): string {
  const total = row.submission_count ?? 0
  if (!total) return '--'
  return `${Math.round(((row.accepted_count ?? 0) / total) * 100)}%`
}

onMounted(() => {
  load()
  loadTagOptions()
})

const columns = computed<DataTableColumns<ProblemSummary>>(() => [
  {
    title: '',
    key: 'solved',
    width: 72,
    render: (row) => renderSolveMark(t, row.solved),
  },
  {
    title: t('problems.list.name'),
    key: 'title',
    minWidth: 280,
    render(row) {
      return h('div', { class: 'problem-name' }, [
        h('div', { class: 'problem-name__row' }, [
          h('strong', null, row.title),
          row.visibility === 'private'
            ? h(NTag, { size: 'small', bordered: false, type: 'error' }, { default: () => t('problems.list.privateTag') })
            : null,
        ])      
      ])
    },
  },
  {
    title: t('problems.list.tags'),
    key: 'tags',
    width: 200,
    render(row) {
      const tags = row.tags ?? []
      if (tags.length === 0) return null
      return h('div', { class: 'problem-tags' }, [
        h(NTag,
          {
            size: 'small',
            round: true,
            bordered: false,
            color: tags[0].color ? { color: tags[0].color, textColor: '#fff' } : undefined,
          },
          { default: () => tags[0].name },
        ),
        tags.length > 1
          ? h(NTag, { size: 'small', round: true, bordered: false }, { default: () => `+${tags.length - 1}` })
          : null,
      ])
    },
  },
  {
    title: t('problems.list.limits'),
    key: 'limits',
    width: 180,
    render: (row) => `${row.time_limit_ms} ms / ${row.memory_limit_mb} MB`,
  },
  {
    title: t('problems.list.difficulty'),
    key: 'difficulty',
    width: 90,
    render: (row) => ((row.difficulty ?? null) === null ? '--' : String(row.difficulty)),
  },
  {
    title: t('problems.list.passRate'),
    key: 'pass_rate',
    width: 100,
    render: (row) => passRate(row),
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
  <!-- 题库中心与其他列表工作台统一：page-fill 视口锁定，表格区内部滚动 -->
  <WorkbenchShell>
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('problems.list.search')"
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
      <n-select
        v-model:value="tag"
        style="width: 150px"
        clearable
        :options="tagOptions"
        :placeholder="t('problems.list.tag')"
        @update:value="changeTag"
      />
      <div class="difficulty-filter">
        <n-input-number
          v-model:value="difficultyMin"
          :min="0"
          :show-button="false"
          clearable
          :placeholder="t('problems.list.difficultyMin')"
          class="difficulty-filter__input"
        />
        <span class="difficulty-filter__sep" aria-hidden="true">—</span>
        <n-input-number
          v-model:value="difficultyMax"
          :min="0"
          :show-button="false"
          clearable
          :placeholder="t('problems.list.difficultyMax')"
          class="difficulty-filter__input"
        />
      </div>
      <template #actions>
        <n-checkbox v-if="isManager" v-model:checked="mineOnly" @update:checked="onSearch">
          {{ t('problems.list.mineOnly') }}
        </n-checkbox>
        <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
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
        <span class="pager__total">{{ t('problems.list.totalCount', { count: total }) }}</span>
      </template>
    </PaginatedDataTable>
  </WorkbenchShell>
</template>

<style scoped>
.problem-name {
  display: grid;
  gap: 4px;
}
.problem-name__row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.problem-name strong {
  font-size: 14px;
}
.problem-name span {
  color: var(--app-text-secondary);
  font-size: 12px;
}
.difficulty-filter {
  display: flex;
  align-items: center;
  gap: 6px;
}
/* 96px：容纳「最低难度」占位符不截断；与工具栏其余控件统一默认高度 */
.difficulty-filter__input {
  width: 96px;
}
.difficulty-filter__sep {
  color: var(--app-text-secondary);
}
.problem-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
</style>
