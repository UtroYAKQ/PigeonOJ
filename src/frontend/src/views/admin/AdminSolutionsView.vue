<script setup lang="ts">
/**
 * 题解管理（docs/contracts/admin.md「社区内容管理」）：全状态列表 + 预览弹窗 +
 * 评论治理下钻（不设独立评论列表页，评论从所属题解预览弹窗内查看与处置）。
 * 举报处理页经 ?solution=<id>&comment=<id> 跳转本页预览并锚定评论。
 */
import { computed, h, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { NButton, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import { adminGetSolution, adminListSolutions, adminSetSolutionStatus } from '@/api/community'
import { listProblems } from '@/api/problems'
import BaseAvatar from '@/components/BaseAvatar.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import CommentSection from '@/components/community/CommentSection.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { usePagination } from '@/composables/usePagination'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import type { AdminSolution, SolutionStatus } from '@/types'

const { t } = useI18n()
const route = useRoute()

const loading = ref(false)
const list = ref<AdminSolution[]>([])
const { page, pageSize, total, changePage, changeSize, resetPage, beginLoad, isCurrent } =
  usePagination()
const query = reactive({
  keyword: '',
  status: null as SolutionStatus | null,
  problem_id: null as string | null,
})

/** 题目筛选（远程搜索下拉）：复用题目管理同款接口（scope=mine，admin 见全量题目） */
const problemOptions = ref<Array<{ label: string; value: string }>>([])
const problemSearching = ref(false)
let problemSearchTimer: ReturnType<typeof setTimeout> | null = null

async function fetchProblemOptions(keyword: string) {
  problemSearching.value = true
  try {
    const res = await listProblems({
      scope: 'mine',
      keyword: keyword || undefined,
      page: 1,
      page_size: 20,
    })
    problemOptions.value = res.items.map((p) => ({ label: p.title, value: p.id }))
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
  } finally {
    problemSearching.value = false
  }
}

function onProblemSearch(keyword: string) {
  if (problemSearchTimer) clearTimeout(problemSearchTimer)
  problemSearchTimer = setTimeout(() => void fetchProblemOptions(keyword), 300)
}

/** 预览弹窗：题解全文 + 评论区（admin 模式含被删评论与恢复操作） */
const previewVisible = ref(false)
const previewRow = ref<AdminSolution | null>(null)
const previewDetail = ref<{ content: string } | null>(null)
const previewLoading = ref(false)
const highlightCommentId = ref<string | null>(null)

const statusOptions = computed(() => [
  { label: t('problems.solutions.status.published'), value: 'published' as SolutionStatus },
  { label: t('problems.solutions.status.removed'), value: 'removed' as SolutionStatus },
])

const STATUS_TAG: Record<SolutionStatus, 'success' | 'error'> = {
  published: 'success',
  removed: 'error',
}

async function load() {
  const seq = beginLoad()
  loading.value = true
  try {
    const res = await adminListSolutions({
      page: page.value,
      page_size: pageSize.value,
      status: query.status ?? undefined,
      keyword: query.keyword || undefined,
      problem_id: query.problem_id ?? undefined,
    })
    if (!isCurrent(seq)) return
    list.value = res.items
    total.value = res.total
  } catch (e) {
    if (!isCurrent(seq)) return
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
  } finally {
    if (isCurrent(seq)) loading.value = false
  }
}
onMounted(() => {
  load()
  void fetchProblemOptions('')
  // 举报处理页联动：?solution=<id>&comment=<id> 打开预览并锚定评论
  const solutionParam = route.query.solution
  if (typeof solutionParam === 'string' && solutionParam) {
    const commentParam = typeof route.query.comment === 'string' ? route.query.comment : null
    void openPreviewById(solutionParam, commentParam)
  }
})
function onSearch() {
  resetPage()
  load()
}

async function openPreviewById(id: string, commentId: string | null) {
  // 举报处理页直达：不经列表，按 id 拉管理详情后直接打开预览
  try {
    const row = await adminGetSolution(id)
    await openPreview(row, commentId)
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('admin.solutions.previewNotFound'))
  }
}

async function openPreview(row: AdminSolution, commentId: string | null = null) {
  previewRow.value = row
  previewDetail.value = null
  highlightCommentId.value = commentId
  previewVisible.value = true
  previewLoading.value = true
  try {
    const { getSolution } = await import('@/api/community')
    previewDetail.value = await getSolution(row.id)
  } catch (e) {
    message.error(e instanceof Error ? e.message : t('common.loadFailed'))
    previewVisible.value = false
  } finally {
    previewLoading.value = false
  }
}

function toggleStatus(row: AdminSolution) {
  const removing = row.status !== 'removed'
  const run = () =>
    adminSetSolutionStatus(row.id, removing ? 'removed' : 'published').then(() => {
      row.status = removing ? 'removed' : 'published'
      if (previewRow.value?.id === row.id) previewRow.value = { ...row }
    })
  if (removing) {
    confirmAsyncDialog({
      title: t('admin.solutions.removeTitle'),
      content: t('admin.solutions.removeConfirm', { title: row.title }),
      positiveText: t('action.confirm'),
      action: run,
      successMessage: t('common.success'),
    })
  } else {
    void run().then(() => message.success(t('common.success')))
  }
}

const columns = computed<DataTableColumns<AdminSolution>>(() => [
  {
    title: t('admin.solutions.title'),
    key: 'title',
    minWidth: 220,
    ellipsis: { tooltip: true },
    render: (row) =>
      h(
        'a',
        {
          class: 'cell-link',
          onClick: () => openPreview(row),
        },
        row.title,
      ),
  },
  {
    title: t('admin.solutions.problem'),
    key: 'problem',
    minWidth: 180,
    ellipsis: { tooltip: true },
    render: (row) => row.problem.title,
  },
  {
    title: t('admin.solutions.author'),
    key: 'author',
    width: 140,
    render(row) {
      return h('div', { class: 'cell-author' }, [
        h(BaseAvatar, {
          src: row.author.avatar_url ?? undefined,
          name: row.author.nickname,
          size: 24,
        }),
        h('span', row.author.nickname),
      ])
    },
  },
  {
    title: t('admin.solutions.status'),
    key: 'status',
    width: 90,
    render: (row) =>
      h(
        NTag,
        { size: 'small', type: STATUS_TAG[row.status], bordered: false },
        { default: () => t(`problems.solutions.status.${row.status}`) },
      ),
  },
  {
    title: t('admin.solutions.commentCount'),
    key: 'comment_count',
    width: 80,
    render: (row) => String(row.comment_count),
  },
  {
    title: t('admin.solutions.updatedAt'),
    key: 'updated_at',
    width: 160,
    render: (row) => formatDateTime(row.updated_at),
  },
  {
    title: t('admin.solutions.actions'),
    key: 'actions',
    width: 150,
    fixed: 'right',
    render(row) {
      return h('div', { class: 'cell-actions' }, [
        h(
          NButton,
          { text: true, type: 'primary', onClick: () => openPreview(row) },
          { default: () => t('admin.solutions.preview') },
        ),
        h(
          NButton,
          {
            text: true,
            type: row.status === 'removed' ? 'success' : 'warning',
            onClick: () => toggleStatus(row),
          },
          {
            default: () =>
              row.status === 'removed' ? t('admin.solutions.restore') : t('admin.solutions.remove'),
          },
        ),
      ])
    },
  },
])
</script>

<template>
  <WorkbenchShell>
    <SearchFilterBar
      :keyword="query.keyword"
      :placeholder="t('admin.solutions.search')"
      @update:keyword="
        (v: string) => {
          query.keyword = v
        }
      "
      @search="onSearch"
      @reset="onSearch"
    >
      <n-select
        v-model:value="query.problem_id"
        filterable
        clearable
        remote
        :loading="problemSearching"
        :options="problemOptions"
        :placeholder="t('admin.solutions.problemFilter')"
        style="width: 240px"
        @search="onProblemSearch"
        @update:value="onSearch"
      />
      <n-select
        v-model:value="query.status"
        clearable
        style="width: 150px"
        :options="statusOptions"
        :placeholder="t('common.allStatus')"
        @update:value="onSearch"
      />
      <template #actions>
        <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="onSearch" />
      </template>
    </SearchFilterBar>

    <PaginatedDataTable
      show-size-picker
      :columns="columns"
      :data="list"
      :loading="loading"
      :total="total"
      v-model:page="page"
      v-model:page-size="pageSize"
      :page-sizes="[10, 20, 50]"
      :empty-text="t('admin.solutions.empty')"
      :table-props="{ scrollX: 1100 }"
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
    />

    <!-- 题解预览：全文 + 评论治理（admin 模式含被删评论与恢复） -->
    <n-modal
      v-model:show="previewVisible"
      preset="card"
      style="width: min(880px, 94vw)"
      :title="previewRow?.title"
    >
      <n-spin :show="previewLoading">
        <div v-if="previewRow" class="preview">
          <div class="preview__meta">
            <BaseAvatar
              :src="previewRow.author.avatar_url ?? undefined"
              :name="previewRow.author.nickname"
              :size="26"
            />
            <span class="preview__author">{{ previewRow.author.nickname }}</span>
            <span>{{ formatDateTime(previewRow.created_at) }}</span>
            <span class="preview__problem">{{ previewRow.problem.title }}</span>
            <n-tag size="small" :type="STATUS_TAG[previewRow.status]" bordered>
              {{ t(`problems.solutions.status.${previewRow.status}`) }}
            </n-tag>
            <span class="preview__spacer" />
            <n-button
              size="tiny"
              :type="previewRow.status === 'removed' ? 'success' : 'warning'"
              secondary
              @click="toggleStatus(previewRow)"
            >
              {{
                previewRow.status === 'removed'
                  ? t('admin.solutions.restore')
                  : t('admin.solutions.remove')
              }}
            </n-button>
          </div>
          <div v-if="previewDetail" class="preview__content">
            <MarkdownView :source="previewDetail.content" />
          </div>
          <CommentSection
            target-type="solution"
            :target-id="previewRow.id"
            admin-mode
            :highlight-comment-id="highlightCommentId"
          />
        </div>
      </n-spin>
    </n-modal>
  </WorkbenchShell>
</template>

<style scoped>
.cell-link {
  color: var(--app-primary);
  cursor: pointer;
}
.cell-link:hover {
  text-decoration: underline;
}
.cell-author {
  display: flex;
  align-items: center;
  gap: 6px;
}
.preview__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.preview__author {
  font-weight: 600;
  color: var(--app-text);
}
.preview__problem {
  padding: 2px 8px;
  border-radius: 3px;
  background: var(--app-muted-bg);
}
.preview__spacer {
  flex: 1;
}
.preview__content {
  margin: 12px 0 18px;
  padding: 12px 16px;
  border: 1px solid var(--app-border);
  border-radius: 4px;
  max-height: 45vh;
  overflow: auto;
}
</style>
