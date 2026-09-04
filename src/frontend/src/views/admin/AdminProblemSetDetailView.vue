<script setup lang="ts">
/**
 * 题单详情（管理后台，admin/tutor）：点进来即编排。
 * 左 4/12：题单标题 / 元信息 / Markdown 说明；右 8/12：题目列表
 * （行内上移 / 下移 / 移除即时保存，「添加题目」打开题库选择器弹窗）。
 */
import { computed, h, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NButton, NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import MarkdownView from '@/components/MarkdownView.vue'
import ProblemPicker from '@/components/problemsets/ProblemPicker.vue'
import RefreshButton from '@/components/RefreshButton.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import {
  archiveProblemSet,
  getProblemSet,
  replaceProblemSetItems,
} from '@/api/problemSets'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import type { ProblemSetDetail, ProblemSetItem, ProblemSummary } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const setId = String(route.params.id)
const loading = ref(false)
const detail = ref<ProblemSetDetail | null>(null)
/** 编排操作瞬时保存中（行内 ops 与添加按钮共用，避免并发写） */
const arranging = ref(false)
const pickerShow = ref(false)

async function load() {
  loading.value = true
  try {
    detail.value = await getProblemSet(setId)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
    router.push('/admin/problem-sets')
  } finally {
    loading.value = false
  }
}
onMounted(load)

/** 行内编排落库：以当前列表全量替换（含 sort_order），成功后刷新基线 */
async function persistItems(items: ProblemSetItem[]) {
  arranging.value = true
  try {
    await replaceProblemSetItems(setId, {
      items: items.map((it, i) => ({ problem_id: it.problem_id, sort_order: i })),
    })
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.saveFailed'))
    await load() // 失败回滚到服务器权威状态
  } finally {
    arranging.value = false
  }
}

function onPicked(problem: ProblemSummary) {
  if (!detail.value) return
  if (detail.value.items.some((it) => it.problem_id === problem.id)) return
  const items = [
    ...detail.value.items,
    {
      problem_id: problem.id,
      title: problem.title,
      difficulty: problem.difficulty ?? null,
      time_limit_ms: problem.time_limit_ms,
      memory_limit_mb: problem.memory_limit_mb,
      sort_order: detail.value.items.length,
    },
  ]
  detail.value = { ...detail.value, items }
  void persistItems(items)
}

function removeItem(row: ProblemSetItem) {
  if (!detail.value) return
  const items = detail.value.items.filter((it) => it.problem_id !== row.problem_id)
  detail.value = { ...detail.value, items }
  void persistItems(items)
}

function moveItem(index: number, delta: -1 | 1) {
  if (!detail.value) return
  const target = index + delta
  if (target < 0 || target >= detail.value.items.length) return
  const items = [...detail.value.items]
  ;[items[index], items[target]] = [items[target], items[index]]
  detail.value = { ...detail.value, items: items.map((it, i) => ({ ...it, sort_order: i })) }
  void persistItems(detail.value.items)
}

/** 拖拽排序（原生 HTML5 DnD，零依赖）：dragover 高亮目标行，drop 后整体重排并落库 */
const dragIndex = ref<number | null>(null)
const overIndex = ref<number | null>(null)

function onDragStart(index: number, event: DragEvent) {
  dragIndex.value = index
  if (event.dataTransfer) {
    // dataTransfer 必须写入数据，否则 Firefox 不触发 dragover/drop
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(index))
  }
}

function onDragOver(index: number, event: DragEvent) {
  if (dragIndex.value === null) return
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  if (overIndex.value !== index) overIndex.value = index
}

function onDrop(index: number) {
  if (dragIndex.value === null || !detail.value) return resetDragState()
  const from = dragIndex.value
  if (from !== index) {
    const items = [...detail.value.items]
    const [moved] = items.splice(from, 1)
    items.splice(index, 0, moved)
    detail.value = { ...detail.value, items: items.map((it, i) => ({ ...it, sort_order: i })) }
    void persistItems(detail.value.items)
  }
  resetDragState()
}

function resetDragState() {
  dragIndex.value = null
  overIndex.value = null
}

function rowProps(row: ProblemSetItem, index: number) {
  return {
    draggable: !arranging.value,
    class:
      dragIndex.value === index
        ? 'row-dragging'
        : overIndex.value === index && dragIndex.value !== null
          ? 'row-drop-target'
          : '',
    onDragstart: (event: DragEvent) => onDragStart(index, event),
    onDragover: (event: DragEvent) => onDragOver(index, event),
    onDrop: () => onDrop(index),
    onDragend: resetDragState,
  }
}

function goEdit() {
  router.push(`/admin/problem-sets/${setId}/edit`)
}

function doArchive() {
  confirmAsyncDialog({
    title: t('problemSets.detail.archive'),
    content: t('problemSets.detail.archiveConfirm'),
    positiveText: t('problemSets.detail.archive'),
    action: () => archiveProblemSet(setId),
    successMessage: t('common.success'),
    onAfterSuccess: () => {
      router.push('/admin/problem-sets')
    },
  })
}

function rowKey(row: ProblemSetItem) {
  return row.problem_id
}

const columns = computed<DataTableColumns<ProblemSetItem>>(() => [
  {
    title: t('problemSets.detail.orderLabel'),
    key: 'order',
    width: 52,
    render: (_row, index) => h('span', { class: 'item-order' }, String(index + 1)),
  },
  {
    title: t('problemSets.list.titleLabel'),
    key: 'title',
    minWidth: 200,
    render: (row) => h('span', { class: 'item-title' }, row.title),
  },
  {
    title: t('problemSets.detail.difficulty'),
    key: 'difficulty',
    width: 80,
    render: (row) => ((row.difficulty ?? null) === null ? '--' : String(row.difficulty)),
  },
  {
    title: t('problems.list.limits'),
    key: 'limits',
    width: 150,
    render: (row) => `${row.time_limit_ms ?? '--'} ms / ${row.memory_limit_mb ?? '--'} MB`,
  },
  {
    title: '',
    key: 'actions',
    width: 150,
    render(row) {
      const index = detail.value?.items.findIndex((it) => it.problem_id === row.problem_id) ?? -1
      const last = (detail.value?.items.length ?? 0) - 1
      return h('div', { class: 'item-ops' }, [
        h(
          NButton,
          {
            text: true,
            size: 'tiny',
            disabled: index === 0 || arranging.value,
            'aria-label': 'up',
            onClick: () => moveItem(index, -1),
          },
          { default: () => '↑' },
        ),
        h(
          NButton,
          {
            text: true,
            size: 'tiny',
            disabled: index === last || arranging.value,
            'aria-label': 'down',
            onClick: () => moveItem(index, 1),
          },
          { default: () => '↓' },
        ),
        h(
          NButton,
          {
            text: true,
            size: 'tiny',
            type: 'error',
            disabled: arranging.value,
            onClick: () => removeItem(row),
          },
          { default: () => t('problemSets.detail.remove') },
        ),
      ])
    },
  },
])

const chosenIds = computed(() => new Set((detail.value?.items ?? []).map((it) => it.problem_id)))
</script>

<template>
  <WorkbenchShell>
    <template #header>
      <div class="detail-head">
        <strong class="detail-head__title">{{
          detail?.title ?? t('problemSets.detail.title')
        }}</strong>
        <n-tag
          v-if="detail"
          size="small"
          :bordered="false"
          :type="detail.visibility === 'public' ? 'info' : 'error'"
        >
          {{
            t(
              detail.visibility === 'public'
                ? 'problemSets.list.visibilityPublic'
                : 'problemSets.list.visibilityPrivate',
            )
          }}
        </n-tag>
        <n-tag v-if="detail?.status === 'archived'" type="warning" size="small">
          {{ t('problemSets.detail.archived') }}
        </n-tag>
      </div>
    </template>
    <template #header-extra>
      <div v-if="detail" class="detail-actions">
        <n-button size="small" @click="goEdit">
          {{ t('problemSets.detail.edit') }}
        </n-button>
        <n-button
          v-if="detail.status === 'active'"
          size="small"
          type="error"
          secondary
          @click="doArchive"
        >
          {{ t('problemSets.detail.archive') }}
        </n-button>
      </div>
      <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load" />
    </template>

    <n-spin :show="loading">
      <div v-if="detail" class="detail-grid">
        <!-- 左框：题单介绍（内部滚动）+ 元信息钉底 -->
        <section class="panel">
          <div class="panel__head">
            <span>{{ t('problemSets.list.descLabel') }}</span>
          </div>
          <div class="panel__body panel__body--scroll">
            <MarkdownView v-if="detail.description" :source="detail.description" />
            <n-empty
              v-else
              size="small"
              :description="t('problemSets.detail.noDescription')"
              class="panel-empty"
            />
          </div>
        </section>

        <!-- 右框：题目列表（点进来即编排，表体内部滚动） -->
        <section class="panel">
          <div class="panel__head">
            <span>{{ t('problemSets.detail.problems') }} · {{ detail.items.length }}</span>
            <n-button
              type="primary"
              size="small"
              :disabled="detail.status === 'archived' || arranging"
              @click="pickerShow = true"
            >
              {{ t('problemSets.form.pickAdd') }}
            </n-button>
          </div>
          <div class="panel__body panel__body--flush">
            <n-data-table
              size="small"
              :columns="columns"
              :data="detail.items"
              :loading="loading"
              :bordered="false"
              :bottom-bordered="false"
              :row-key="rowKey"
              :row-props="rowProps"
              :empty="t('problemSets.detail.empty')"
            />
          </div>
        </section>
      </div>
    </n-spin>

    <ProblemPicker
      v-model:show="pickerShow"
      :chosen-ids="chosenIds"
      @add="onPicked"
    />
  </WorkbenchShell>
</template>

<style scoped>
.detail-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.detail-head__title {
  font-size: 16px;
}
.detail-actions {
  display: inline-flex;
  gap: 8px;
  margin-right: 8px;
}
/* 布局思路（与前台题单详情同款）：固定部分自然排列，双框显式定高
   calc(100dvh - 220px)（预算：顶栏 60 + 页面内边距 28 + 卡片头 ~60 + 卡片内边距 ~40
   + 面板头/脚余量 ~32），不依赖 n-spin 内部结构传 flex 高度；
   超出内容在框内滚动，页面级不出滚动条。 */
.detail-grid {
  display: grid;
  grid-template-columns: minmax(0, 4fr) minmax(0, 8fr);
  gap: 20px;
  height: calc(100dvh - 190px);
  min-height: 360px;
}
.panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-lg);
  background: var(--app-card-bg);
  overflow: hidden; /* 圆角裁切内部滚动区 */
}
.panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-shrink: 0;
  padding: 12px 16px 8px;
  font-size: 14px;
  font-weight: 600;
}
.panel__body {
  flex: 1;
  min-height: 0;
}
.panel__body--scroll {
  overflow: auto;
  padding: 4px 16px 12px;
}
.panel__body--flush {
  overflow: auto;
}
.panel-empty {
  padding: 32px 0;
  display: grid;
  place-items: center;
}
.item-order {
  color: var(--app-text-secondary);
  font-size: 12px;
}
/* 拖拽排序视觉：拖起行半透明，目标行顶部插入线指示落点 */
.item-order {
  cursor: grab;
}
:deep(.row-dragging) {
  opacity: 0.45;
}
:deep(.row-drop-target) td {
  box-shadow: inset 0 2px 0 0 var(--app-primary);
}
.item-title {
  font-size: 13px;
}
.item-ops {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
@media (max-width: 960px) {
  /* 窄屏：单列，两框自适应高度，不锁视口 */
  .detail-grid {
    height: auto;
    grid-template-columns: 1fr;
  }
  .panel__body--scroll,
  .panel__body--flush {
    overflow: visible;
  }
}
</style>
