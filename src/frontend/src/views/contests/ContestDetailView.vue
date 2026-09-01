<script setup lang="ts">
/**
 * 比赛详情：主页（hero + 数据瓦片 + 时间轴 + 说明）/ 题目 / 榜单 / 提交记录 四个 tab。
 * 题目进入比赛上下文写题页（统一入口交题）；榜单封榜展示冻结快照，
 * 解冻为 admin/tutor 手动操作（重算回填封榜期结果）；进行中榜单 15s 轮询。
 * 提交记录比赛期间对所有人隐藏，赛后开放（行点击进上下文内评测结果页）。
 */
import { computed, h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NTag } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'

import RefreshButton from '@/components/RefreshButton.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import StatusTag from '@/components/StatusTag.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import {
  getContest,
  getContestBoard,
  listContestCellAccepted,
  listContestSubmissions,
  registerContest,
  unfreezeContestBoard,
} from '@/api/contests'
import { confirmAsyncDialog, message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import { usePagination } from '@/composables/usePagination'
import type {
  Board,
  BoardCell,
  ContestDetail,
  ContestProblemItem,
  ContestSubmissionItem,
} from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const loading = ref(false)
const detail = ref<ContestDetail | null>(null)
const registering = ref(false)
const activeTab = ref<'home' | 'problems' | 'board' | 'submissions'>('home')

// ---- 提交记录（tab 激活时懒加载；比赛期间所有人不可见，赛后开放） ----
const submissions = ref<ContestSubmissionItem[]>([])
const subsLoading = ref(false)
const {
  page: subsPage,
  pageSize: subsPageSize,
  total: subsTotal,
  changePage,
  changeSize,
  beginLoad: subsBeginLoad,
  isCurrent: subsIsCurrent,
} = usePagination()

/** 比赛期间（end_time 之前）提交记录对所有人隐藏 */
const subsLocked = computed(
  () => !!detail.value && Date.now() < new Date(detail.value.end_time).getTime(),
)
/** 赛后仅参赛者与管理角色可见 */
const subsAllowed = computed(() => {
  const d = detail.value
  return !!d && (d.my_registration === 'registered' || d.can_manage)
})

async function loadSubmissions(silent = false) {
  const seq = subsBeginLoad()
  subsLoading.value = !silent
  try {
    const result = await listContestSubmissions(String(route.params.id), {
      page: subsPage.value,
      page_size: subsPageSize.value,
    })
    if (!subsIsCurrent(seq)) return
    submissions.value = result.items
    subsTotal.value = result.total
  } catch (error) {
    if (!subsIsCurrent(seq)) return
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (subsIsCurrent(seq)) subsLoading.value = false
  }
}

function changeSubsPage(value: number) {
  changePage(value)
  void loadSubmissions()
}

function changeSubsPageSize(value: number) {
  changeSize(value)
  void loadSubmissions()
}

function openSubmission(row: ContestSubmissionItem) {
  router.push(`/contests/${String(route.params.id)}/submissions/${row.id}`)
}

function submissionRowProps(row: ContestSubmissionItem) {
  return {
    style: 'cursor: pointer;',
    onClick: () => openSubmission(row),
  }
}

// ---- 榜单（tab 激活时懒加载；比赛进行中每 15s 静默轮询） ----
const board = ref<Board | null>(null)
const boardLoading = ref(false)
let pollTimer: number | null = null

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    detail.value = await getContest(String(route.params.id))
  } catch (error) {
    if (!silent) message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (!silent) loading.value = false
  }
}

async function loadBoard(silent = false) {
  boardLoading.value = !silent
  try {
    board.value = await getContestBoard(String(route.params.id))
  } catch (error) {
    if (!silent) message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    boardLoading.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'board' && !board.value) void loadBoard()
  if (
    tab === 'submissions' &&
    !subsLocked.value &&
    subsAllowed.value &&
    !submissions.value.length
  ) {
    void loadSubmissions()
  }
})

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(() => {
  void load()
  pollTimer = window.setInterval(() => {
    if (
      activeTab.value === 'board' &&
      detail.value?.status === 'running' &&
      !detail.value.board_frozen
    ) {
      void loadBoard(true)
    }
  }, 15000)
})
onBeforeUnmount(stopPolling)

async function register() {
  if (!detail.value) return
  registering.value = true
  try {
    await registerContest(detail.value.id)
    message.success(t('common.success'))
    await load(true)
    if (activeTab.value === 'board') void loadBoard(true)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    registering.value = false
  }
}

/** 手动解冻（admin/tutor）：重算榜单回填封榜期结果 */
function doUnfreeze() {
  confirmAsyncDialog({
    title: t('contests.detail.unfreeze'),
    content: t('contests.detail.unfreezeConfirm'),
    positiveText: t('contests.detail.unfreeze'),
    action: () => unfreezeContestBoard(String(route.params.id)),
    successMessage: t('common.success'),
    onAfterSuccess: async () => {
      await load(true)
      await loadBoard(true)
    },
  })
}

const statusMeta = computed(() => {
  const map = {
    running: { label: t('contests.statusRunning'), type: 'success' as const },
    scheduled: { label: t('contests.statusScheduled'), type: 'info' as const },
    finished: { label: t('contests.statusFinished'), type: 'default' as const },
  }
  return map[detail.value?.status ?? 'scheduled']
})

const initial = computed(() => (detail.value?.title || '?').trim().charAt(0).toUpperCase())

// ---------------- 主页：时间轴 ----------------

interface Milestone {
  label: string
  time: string
  done: boolean
  current: boolean
}

const schedule = computed<Milestone[]>(() => {
  const d = detail.value
  if (!d) return []
  const now = Date.now()
  const items = [
    { label: t('contests.list.regStartTime'), time: d.register_start_time },
    { label: t('contests.list.regEndTime'), time: d.register_end_time },
    { label: t('contests.list.startTime'), time: d.start_time },
    { label: t('contests.list.endTime'), time: d.end_time },
  ]
  return items.map((item) => {
    const done = now >= new Date(item.time).getTime()
    return { label: item.label, time: formatDateTime(item.time), done, current: false }
  })
})

// ---------------- 题目列表 ----------------

const problemColumns = computed<DataTableColumns<ContestProblemItem>>(() => [
  {
    title: t('contests.detail.letter'),
    key: 'letter',
    width: 70,
    render: (row) => row.letter ?? '--',
  },
  {
    title: t('problemSets.list.titleLabel'),
    key: 'title',
    minWidth: 280,
    render: (row) => h('strong', null, row.title),
  },
  {
    title: t('contests.list.problemScore'),
    key: 'score',
    width: 100,
    render: (row) => (row.score > 0 ? String(row.score) : '--'),
  },
  {
    title: t('contests.detail.difficulty'),
    key: 'difficulty',
    width: 90,
    render: (row) => ((row.difficulty ?? null) === null ? '--' : String(row.difficulty)),
  },
])

function goProblem(row: ContestProblemItem) {
  if (!detail.value) return
  router.push(`/contests/${detail.value.id}/problems/${row.problem_id}`)
}

function problemRowProps(row: ContestProblemItem) {
  return {
    style: 'cursor: pointer;',
    onClick: () => goProblem(row),
  }
}

// ---------------- 榜单（重设计：固定前两列 + 双行题头 + 药丸格；赛后 AC 格可点看成功提交） ----------------

const isAcM = computed(() => board.value?.rule_type === 'ACM')

interface Row {
  rank: number
  user_id: string
  nickname: string
  solved: number
  metric: number
  cells: BoardCell[]
}

/** 榜单 AC 格可点击：与提交记录同一窗口与角色门控（封榜格子保持冻结态，不可点） */
const boardClickable = computed(() => !subsLocked.value && subsAllowed.value)

/** 榜单单格成功提交弹窗（赛后点击 AC 格） */
const cellModal = ref({
  show: false,
  loading: false,
  title: '',
  items: [] as ContestSubmissionItem[],
})

async function openCell(row: Row, cell: BoardCell) {
  cellModal.value = {
    show: true,
    loading: true,
    title: `${cell.letter ?? ''} · ${row.nickname}`,
    items: [],
  }
  try {
    cellModal.value.items = await listContestCellAccepted(
      String(route.params.id),
      row.user_id,
      cell.problem_id,
    )
  } catch (error) {
    cellModal.value.show = false
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    cellModal.value.loading = false
  }
}

const cellColumns = computed<DataTableColumns<ContestSubmissionItem>>(() => [
  {
    title: t('problems.detail.status'),
    key: 'status',
    minWidth: 140,
    render: (row) => h(StatusTag, { status: row.status }),
  },
  {
    title: t('problems.submission.score'),
    key: 'score',
    width: 80,
    render: (row) => row.score ?? '-',
  },
  {
    title: t('problems.submission.time'),
    key: 'time',
    width: 100,
    render: (row) => `${row.time_used_ms ?? '-'} ms`,
  },
  {
    title: t('problems.submission.memory'),
    key: 'memory',
    width: 110,
    render: (row) => `${row.memory_used_kb ?? '-'} KB`,
  },
  { title: t('problems.detail.language'), key: 'language', width: 110 },
  {
    title: t('contests.submissions.submitTime'),
    key: 'created_at',
    width: 170,
    render: (row) => formatDateTime(row.created_at),
  },
])

function cellRowProps(row: ContestSubmissionItem) {
  return {
    style: 'cursor: pointer;',
    onClick: () => {
      cellModal.value.show = false
      router.push(`/contests/${String(route.params.id)}/submissions/${row.id}`)
    },
  }
}

const boardColumns = computed<DataTableColumns<Row>>(() => {
  if (!board.value) return []
  const letterColumns = (board.value.rows[0]?.cells ?? []).map((cell, index) => ({
    title: () =>
      h('div', { class: 'cell-head' }, [
        h('span', { class: 'cell-head__letter' }, cell.letter ?? String(index + 1)),
        !isAcM.value && cell.problem_score > 0
          ? h('span', { class: 'cell-head__score' }, String(cell.problem_score))
          : null,
      ]),
    key: `cell-${cell.problem_id}`,
    width: 92,
    render: (row: Row) => {
      const c = row.cells[index]
      if (!c) return h('span', { class: 'cell-pill cell-pill--idle' }, '·')
      if (c.is_frozen) {
        return h(
          NTag,
          { size: 'small', type: 'warning', bordered: false },
          { default: () => t('contests.board.frozenBadge') },
        )
      }
      const pill = (cls: string, label: string, onClick?: () => void) =>
        onClick
          ? h(
              'button',
              {
                type: 'button',
                class: ['cell-pill', cls, 'cell-pill--link'],
                title: t('contests.board.cellClickableHint'),
                onClick,
              },
              label,
            )
          : h('span', { class: ['cell-pill', cls] }, label)
      const open = () => openCell(row, c)
      if (isAcM.value) {
        if (c.accepted)
          return pill('cell-pill--ac', String(c.penalty), boardClickable.value ? open : undefined)
        if (c.attempts > 0) return pill('cell-pill--try', `-${c.attempts}`)
        return pill('cell-pill--idle', '·')
      }
      if (c.accepted)
        return pill('cell-pill--ac', String(c.score), boardClickable.value ? open : undefined)
      if (c.score > 0) return pill('cell-pill--part', String(c.score))
      if (c.attempts > 0) return pill('cell-pill--try', `-${c.attempts}`)
      return pill('cell-pill--idle', '·')
    },
  }))
  return [
    { title: t('contests.board.rank'), key: 'rank', width: 70, fixed: 'left' },
    { title: t('contests.board.user'), key: 'nickname', minWidth: 140, fixed: 'left' },
    {
      title: t('contests.board.solved'),
      key: 'solved',
      width: 90,
      render: (row: Row) =>
        h('span', { class: 'solved-cell' }, `${row.solved}/${row.cells.length}`),
    },
    {
      title: isAcM.value ? t('contests.board.penalty') : t('contests.board.totalScore'),
      key: 'metric',
      width: 100,
      render: (row: Row) => String(row.metric),
    },
    ...letterColumns,
  ]
})

const boardRows = computed<Row[]>(() => {
  if (!board.value) return []
  return board.value.rows.map((r) => ({
    rank: r.rank,
    user_id: r.user_id,
    nickname: r.nickname,
    solved: r.solved,
    metric: isAcM.value ? r.total_penalty : r.total_score,
    cells: r.cells,
  }))
})

// ---------------- 提交记录 ----------------

const submissionColumns = computed<DataTableColumns<ContestSubmissionItem>>(() => [
  {
    title: t('contests.detail.letter'),
    key: 'letter',
    width: 70,
    render: (row) => row.letter ?? '--',
  },
  {
    title: t('contests.submissions.user'),
    key: 'nickname',
    minWidth: 120,
  },
  {
    title: t('problems.detail.status'),
    key: 'status',
    minWidth: 150,
    render: (row) => h(StatusTag, { status: row.status }),
  },
  {
    title: t('problems.submission.score'),
    key: 'score',
    width: 80,
    render: (row) => row.score ?? '-',
  },
  {
    title: t('problems.submission.time'),
    key: 'time',
    width: 100,
    render: (row) => `${row.time_used_ms ?? '-'} ms`,
  },
  {
    title: t('problems.submission.memory'),
    key: 'memory',
    width: 110,
    render: (row) => `${row.memory_used_kb ?? '-'} KB`,
  },
  { title: t('problems.detail.language'), key: 'language', width: 110 },
  {
    title: t('contests.submissions.submitTime'),
    key: 'created_at',
    width: 170,
    render: (row) => formatDateTime(row.created_at),
  },
])
</script>

<template>
  <WorkbenchShell>
    <template #header>
      <div class="detail-head">
        <strong class="detail-head__title">{{
          detail?.title ?? t('contests.detail.title')
        }}</strong>
        <n-tag size="small" :type="statusMeta.type" :bordered="false">{{ statusMeta.label }}</n-tag>
        <n-tag v-if="detail?.board_frozen" type="warning" size="small" :bordered="false">
          {{ t('contests.boardFrozenTag') }}
        </n-tag>
      </div>
    </template>
    <template #header-extra>
      <div class="detail-actions">
        <n-button
          v-if="detail?.can_register"
          type="primary"
          size="small"
          :loading="registering"
          @click="register"
        >
          {{ t('contests.detail.register') }}
        </n-button>
        <n-tag
          v-else-if="detail?.my_registration === 'registered'"
          type="success"
          size="small"
          :bordered="false"
        >
          {{ t('contests.detail.registered') }}
        </n-tag>
      </div>
      <RefreshButton :loading="loading" :aria-label="t('action.refresh')" @click="load()" />
    </template>

    <n-spin :show="loading" class="detail-spin">
      <div v-if="detail" class="detail-body">
        <n-tabs type="line" v-model:value="activeTab" class="detail-tabs">
          <!-- ======== 主页 ======== -->
          <n-tab-pane name="home" :tab="t('contests.detail.tabHome')">
            <!-- Hero：主色渐变 + 玻璃拟态数据瓦片 -->
            <section class="hero">
              <div class="hero__head">
                <div class="hero__logo">
                  <img v-if="detail.logo" :src="detail.logo" alt="logo" />
                  <span v-else>{{ initial }}</span>
                </div>
                <div class="hero__main">
                  <h2 class="hero__title">{{ detail.title }}</h2>
                  <div class="hero__chips">
                    <span class="hero__chip hero__chip--accent">{{ statusMeta.label }}</span>
                    <span class="hero__chip">{{ detail.rule_type }}</span>
                    <span
                      v-if="detail.my_registration === 'registered'"
                      class="hero__chip hero__chip--ok"
                    >
                      {{ t('contests.detail.registered') }}
                    </span>
                  </div>
                </div>
              </div>
              <div class="hero__stats">
                <div class="glass-tile">
                  <span class="glass-tile__value">{{ detail.problem_count }}</span>
                  <span class="glass-tile__label">{{ t('contests.detail.problems') }}</span>
                </div>
                <div class="glass-tile">
                  <span class="glass-tile__value">{{ detail.registered_count }}</span>
                  <span class="glass-tile__label">{{ t('contests.board.user') }}</span>
                </div>
                <div class="glass-tile">
                  <span class="glass-tile__value">
                    {{
                      detail.freeze_offset_seconds > 0 ? `${detail.freeze_offset_seconds}s` : '--'
                    }}
                  </span>
                  <span class="glass-tile__label">{{ t('contests.list.freezeOffset') }}</span>
                </div>
              </div>
            </section>

            <!-- 双栏：时间轴 / 比赛说明 -->
            <div class="home-grid">
              <section class="panel">
                <h4 class="panel__title">{{ t('contests.detail.schedule') }}</h4>
                <div class="timeline">
                  <div
                    v-for="(m, i) in schedule"
                    :key="m.label"
                    class="timeline__item"
                    :class="{ done: m.done, last: i === schedule.length - 1 }"
                  >
                    <span class="timeline__dot" aria-hidden="true"></span>
                    <div class="timeline__content">
                      <span class="timeline__label">{{ m.label }}</span>
                      <span class="timeline__time">{{ m.time }}</span>
                    </div>
                  </div>
                </div>
              </section>
              <section class="panel">
                <h4 class="panel__title">{{ t('contests.detail.about') }}</h4>
                <MarkdownView
                  v-if="detail.description"
                  :source="detail.description"
                  class="home-desc"
                />
                <div v-else class="home-desc home-desc--empty">
                  {{ t('contests.detail.noDescription') }}
                </div>
              </section>
            </div>
          </n-tab-pane>

          <!-- ======== 题目 ======== -->
          <n-tab-pane name="problems" :tab="t('contests.detail.tabProblems')">
            <n-alert v-if="!detail.can_view_problems" type="info" :bordered="false">
              {{ t('contests.detail.notVisible') }}
            </n-alert>
            <n-data-table
              v-else-if="detail.problems.length"
              :columns="problemColumns"
              :data="detail.problems"
              :bordered="false"
              :bottom-bordered="false"
              :row-props="problemRowProps"
            />
            <div v-else class="detail-empty">
              <n-empty size="large" :description="t('contests.list.problemsEmpty')" />
            </div>
          </n-tab-pane>

          <!-- ======== 榜单 ======== -->
          <n-tab-pane name="board" :tab="t('contests.detail.tabBoard')">
            <div class="board-toolbar">
              <n-alert
                v-if="detail.board_frozen"
                type="warning"
                :bordered="false"
                class="frozen-hint"
              >
                {{ t('contests.frozenHint') }}
              </n-alert>
              <n-button
                v-if="detail.can_manage && detail.board_frozen"
                size="small"
                type="warning"
                secondary
                @click="doUnfreeze"
              >
                {{ t('contests.detail.unfreeze') }}
              </n-button>
            </div>
            <!-- 图例：药丸格语义 + 赛后可点提示 -->
            <div v-if="boardRows.length" class="board-legend">
              <span class="legend-item">
                <span class="cell-pill cell-pill--ac">{{ isAcM ? '0' : '100' }}</span>
                {{ t('contests.board.legendAccepted') }}
              </span>
              <span v-if="!isAcM" class="legend-item">
                <span class="cell-pill cell-pill--part">40</span>
                {{ t('contests.board.legendPartial') }}
              </span>
              <span class="legend-item">
                <span class="cell-pill cell-pill--try">-2</span>
                {{ t('contests.board.legendTried') }}
              </span>
              <span class="legend-item">
                <span class="cell-pill cell-pill--idle">·</span>
                {{ t('contests.board.legendIdle') }}
              </span>
              <span v-if="boardClickable" class="legend-item legend-item--hint">
                {{ t('contests.board.legendClickable') }}
              </span>
            </div>
            <n-data-table
              v-if="boardRows.length"
              class="board-table"
              :columns="boardColumns"
              :data="boardRows"
              :loading="boardLoading"
              :bordered="false"
              :bottom-bordered="false"
              :scroll-x="1000"
              flex-height
              :pagination="{ pageSize: 20, showSizePicker: true, pageSizes: [10, 20, 50] }"
            />
            <div v-else class="detail-empty">
              <n-empty size="large" :description="t('contests.board.empty')" />
            </div>

            <!-- 榜单单格成功提交（赛后点击 AC 格） -->
            <n-modal
              v-model:show="cellModal.show"
              preset="card"
              :title="`${cellModal.title} · ${t('contests.board.successfulSubmissions')}`"
              style="width: min(760px, 92vw)"
            >
              <n-data-table
                size="small"
                :columns="cellColumns"
                :data="cellModal.items"
                :loading="cellModal.loading"
                :bordered="false"
                :bottom-bordered="false"
                :row-props="cellRowProps"
              >
                <template #empty>
                  <n-empty size="small" :description="t('contests.board.emptyCellSubmissions')" />
                </template>
              </n-data-table>
            </n-modal>
          </n-tab-pane>

          <!-- ======== 提交记录 ======== -->
          <n-tab-pane name="submissions" :tab="t('contests.detail.tabSubmissions')">
            <n-alert v-if="subsLocked" type="info" :bordered="false" class="subs-hint">
              {{ t('contests.submissions.hiddenDuringContest') }}
            </n-alert>
            <n-alert v-else-if="!subsAllowed" type="info" :bordered="false" class="subs-hint">
              {{ t('contests.submissions.needsRegistration') }}
            </n-alert>
            <template v-else>
              <PaginatedDataTable
                :columns="submissionColumns"
                :data="submissions"
                :loading="subsLoading"
                :total="subsTotal"
                v-model:page="subsPage"
                v-model:page-size="subsPageSize"
                :page-sizes="[20, 50, 100]"
                :empty-text="t('contests.submissions.empty')"
                :table-props="{ scrollX: 900, rowProps: submissionRowProps }"
                @update:page="changeSubsPage"
                @update:page-size="changeSubsPageSize"
              >
                <template #pager-left>
                  <span class="pager__total">
                    {{ t('contests.submissions.totalCount', { count: subsTotal }) }}
                  </span>
                </template>
              </PaginatedDataTable>
            </template>
          </n-tab-pane>
        </n-tabs>
      </div>
    </n-spin>
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
  align-items: center;
}
/* ---- 分页沉底布局链：卡片内容 → n-spin → tabs → pane 纵向伸展，
     表格区（table-fill）撑满剩余高度，分页条自然贴在 tab 内容底部 ---- */
.detail-spin {
  flex: 1;
  min-height: 320px;
  display: flex;
  flex-direction: column;
}
.detail-spin :deep(.n-spin-content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.detail-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}
.detail-tabs {
  flex: 1;
  min-height: 0;
}
.detail-tabs :deep(.n-tabs-pane-wrapper) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.detail-tabs :deep(.n-tab-pane) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
/* 榜单：flex-height 表格撑满剩余高度（表体内部滚动），分页条贴底 */
.board-table {
  flex: 1;
  min-height: 0;
}

/* ---- Hero：中性底 + 细节点缀（主色仅小面积点缀，不大面积铺色） ---- */
.hero {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 22px 26px;
  border-radius: 16px;
  border: 1px solid var(--app-border);
  background:
    radial-gradient(120% 180% at 0% 0%, rgb(244 81 30 / 4%) 0%, transparent 52%),
    var(--app-muted-bg);
}
.hero__head {
  display: flex;
  gap: 16px;
  align-items: center;
}
.hero__logo {
  width: 72px;
  height: 72px;
  border-radius: 16px;
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--app-card-bg, #fff);
  border: 1px solid var(--app-border);
  font-size: 28px;
  font-weight: 700;
  color: var(--app-text-secondary);
}
.hero__logo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.hero__main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 9px;
}
.hero__title {
  margin: 0;
  font-size: 22px;
  font-weight: 750;
  line-height: 1.25;
  color: var(--app-text);
}
.hero__chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.hero__chip {
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: var(--app-text-secondary);
  background: var(--app-card-bg, #fff);
  border: 1px solid var(--app-border);
}
.hero__chip--accent {
  color: var(--app-primary);
  border-color: var(--app-primary);
  background: var(--app-card-bg, #fff);
}
.hero__chip--ok {
  color: var(--app-success, #18a058);
  border-color: var(--app-success, #18a058);
  background: var(--app-card-bg, #fff);
}
.hero__stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.glass-tile {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 13px 16px;
  border-radius: 12px;
  background: var(--app-card-bg, #fff);
  border: 1px solid var(--app-border);
}
.glass-tile__value {
  font-size: 22px;
  font-weight: 750;
  font-variant-numeric: tabular-nums;
  line-height: 1.15;
  color: var(--app-text);
}
.glass-tile__label {
  font-size: 12px;
  color: var(--app-text-secondary);
}

/* ---- 双栏面板 ---- */
.home-grid {
  display: grid;
  grid-template-columns: 5fr 7fr;
  gap: 16px;
  align-items: start;
}
.panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 18px;
  border: 1px solid var(--app-border);
  border-radius: 12px;
  background: var(--app-card-bg, #fff);
}
.panel__title {
  margin: 0;
  font-size: 13px;
  font-weight: 650;
  color: var(--app-text);
  display: flex;
  align-items: center;
  gap: 8px;
}
.panel__title::before {
  content: '';
  width: 3px;
  height: 14px;
  border-radius: 2px;
  background: var(--app-primary);
}
.home-desc {
  margin: 0;
  font-size: 13px;
  color: var(--app-text);
}
.home-desc--empty {
  color: var(--app-text-secondary);
  padding: 22px 0;
  text-align: center;
}

/* ---- 时间轴 ---- */
.timeline {
  display: flex;
  flex-direction: column;
}
.timeline__item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 7px 0 20px 0;
}
.timeline__item:not(.last)::before {
  content: '';
  position: absolute;
  left: 5px;
  top: 22px;
  bottom: -2px;
  width: 2px;
  background: var(--app-border);
}
.timeline__item.done:not(.last)::before {
  background: var(--app-primary);
  opacity: 0.45;
}
.timeline__dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid var(--app-border);
  background: var(--app-card-bg, #fff);
  flex-shrink: 0;
  z-index: 1;
}
.timeline__item.done .timeline__dot {
  border-color: var(--app-primary);
  background: var(--app-primary);
  box-shadow: 0 0 0 3px rgb(244 81 30 / 15%);
}
.timeline__content {
  display: flex;
  gap: 12px;
  align-items: baseline;
  flex: 1;
  justify-content: space-between;
}
.timeline__label {
  font-size: 13px;
  font-weight: 550;
}
.timeline__time {
  font-size: 13px;
  color: var(--app-text-secondary);
  font-variant-numeric: tabular-nums;
}
.timeline__item.done .timeline__time {
  color: var(--app-text);
}

.detail-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
}
.board-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.subs-hint {
  margin-bottom: 10px;
}
.frozen-hint {
  flex: 1;
}

/* ---- 榜单：双行题头 + 药丸格（色值均由设计令牌 color-mix 派生） ---- */
.cell-head {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  line-height: 1.2;
}
.cell-head__letter {
  font-weight: 650;
}
.cell-head__score {
  font-size: 11px;
  font-weight: 500;
  color: var(--app-text-secondary);
}
.solved-cell {
  font-variant-numeric: tabular-nums;
  color: var(--app-text-secondary);
}
.cell-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 650;
  line-height: 1.5;
  font-variant-numeric: tabular-nums;
}
.cell-pill--ac {
  background: color-mix(in srgb, var(--app-success, #18a058) 14%, transparent);
  color: var(--app-success, #18a058);
}
.cell-pill--part {
  background: color-mix(in srgb, var(--app-info, #2080f0) 12%, transparent);
  color: var(--app-info, #2080f0);
}
.cell-pill--try {
  background: var(--app-muted-bg);
  color: var(--app-text-secondary);
  font-weight: 550;
}
.cell-pill--idle {
  color: var(--app-text-secondary);
  opacity: 0.5;
  font-weight: 500;
}
.cell-pill--link {
  border: 0;
  font: inherit;
  font-size: 13px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
  cursor: pointer;
  transition:
    box-shadow 0.15s ease,
    filter 0.15s ease;
}
.cell-pill--link:hover {
  filter: brightness(1.05);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--app-success, #18a058) 35%, transparent);
}
.board-legend {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 14px;
  margin-bottom: 10px;
  font-size: 12px;
  color: var(--app-text-secondary);
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.legend-item .cell-pill {
  min-width: 0;
  padding: 1px 9px;
  font-size: 12px;
  line-height: 1.5;
}
.legend-item--hint {
  color: var(--app-primary);
  font-weight: 550;
}
@media (max-width: 760px) {
  .stats {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
