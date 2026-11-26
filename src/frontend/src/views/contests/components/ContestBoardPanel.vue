<script setup lang="ts">
/**
 * 比赛详情 · 榜单面板：固定前两列 + 双行题头 + 药丸格榜单（tab 激活时懒加载；
 * 比赛进行中每 15s 静默轮询，KeepAlive 切走暂停 / 返回恢复）。
 * 封榜展示冻结快照，解冻为 admin 手动操作；赛后 AC 格可点看成功提交（弹窗）。
 */
import {
  computed,
  h,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  onMounted,
  reactive,
  ref,
  watch,
} from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { DataTableColumns } from 'naive-ui'

import { getContestBoard, listContestCellAccepted } from '@/api/contests'
import { getTeamContestBoard, listTeamContestCellAccepted } from '@/api/teams'
import { message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import { useUserStore } from '@/stores/user'
import RefreshButton from '@/components/RefreshButton.vue'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import PaginatedDataTable from '@/components/PaginatedDataTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import type { Board, BoardCell, ContestDetail, ContestSubmissionItem } from '@/types'

const props = defineProps<{
  detail: ContestDetail
  /** 所属 tab 是否处于激活态（宿主传入，驱动懒加载与轮询） */
  active: boolean
}>()

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

/** 比赛 id：全局路由取 params.id，团队上下文路由取 params.cid */
const contestId = computed(() => String(route.params.cid ?? route.params.id))
const teamId = computed(() => (route.params.teamId ? String(route.params.teamId) : null))
/** 上下文基路径（frontend.md 路由上下文隔离）：团队比赛路由内导航不跳出团队前缀 */
const contextBase = computed(() =>
  teamId.value
    ? `/teams/${teamId.value}/contests/${contestId.value}`
    : `/contests/${contestId.value}`,
)

// ---- 提交记录可见性口径（与提交记录面板一致：AC 格可点性依赖同一窗口与角色门控） ----

/** 比赛期间（end_time 之前）提交记录对参赛者隐藏；管理角色（can_manage，含 admin）随时可见 */
const subsLocked = computed(
  () =>
    !!props.detail &&
    !props.detail.can_manage &&
    Date.now() < new Date(props.detail.end_time).getTime(),
)
/** 赛后向所有登录用户开放（含未报名者）；管理角色随时可见 */
const subsAllowed = computed(() => {
  const d = props.detail
  return (
    !!d && (d.can_manage || (userStore.isLoggedIn && Date.now() >= new Date(d.end_time).getTime()))
  )
})

// ---- 榜单加载（tab 激活时懒加载；比赛进行中每 15s 静默轮询） ----

const board = ref<Board | null>(null)
const boardLoading = ref(false)
let pollTimer: number | null = null

async function loadBoard(silent = false) {
  boardLoading.value = !silent
  try {
    board.value = await (teamId.value
      ? getTeamContestBoard(teamId.value, contestId.value)
      : getContestBoard(contestId.value))
  } catch (error) {
    if (!silent) message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    boardLoading.value = false
  }
}

watch(
  () => props.active,
  (active) => {
    if (active && !board.value) void loadBoard()
  },
)

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPolling() {
  if (pollTimer !== null) return // 已在运行（如 activated 重复触发）
  // 进行中榜单 15s 轮询；须 < 后端 BOARD_CACHE_TTL_RUNNING（contest.py，当前 20s），
  // 使轮询命中读缓存而非每次回源重算（改此值需同步后端 TTL）
  pollTimer = window.setInterval(() => {
    if (props.active && props.detail.status === 'running' && !props.detail.board_frozen) {
      void loadBoard(true)
    }
  }, 15000)
}

// KeepAlive 缓存页：被切走时停轮询（后台不空转），返回时恢复
onMounted(() => {
  startPolling()
})
onDeactivated(() => {
  stopPolling()
})
onActivated(() => {
  startPolling()
})
onBeforeUnmount(() => {
  stopPolling()
})

defineExpose({
  /** 宿主动作（如报名）后静默刷新榜单 */
  refresh: () => loadBoard(true),
})

// ---------------- 榜单（重设计：固定前两列 + 双行题头 + 药丸格；赛后 AC 格可点看成功提交） ----------------

const isAcM = computed(() => board.value?.rule_type === 'ACM')

/** 每题全场首次 AC 的时间戳（一血判定；封榜格不参与，避免提前揭晓） */
const firstAcceptedAt = computed<Record<string, number>>(() => {
  const map: Record<string, number> = {}
  if (!board.value) return map
  for (const row of board.value.rows) {
    for (const cell of row.cells) {
      if (!cell.accepted || !cell.accepted_at || cell.is_frozen) continue
      const ts = Date.parse(cell.accepted_at)
      if (Number.isNaN(ts)) continue
      const cur = map[cell.problem_id]
      if (cur === undefined || ts < cur) map[cell.problem_id] = ts
    }
  }
  return map
})

function isFirstSolve(cell: BoardCell): boolean {
  if (!cell.accepted || !cell.accepted_at || cell.is_frozen) return false
  const ts = Date.parse(cell.accepted_at)
  if (Number.isNaN(ts)) return false
  const first = firstAcceptedAt.value[cell.problem_id]
  return first !== undefined && ts === first
}

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
    cellModal.value.items = await (teamId.value
      ? listTeamContestCellAccepted(teamId.value, contestId.value, row.user_id, cell.problem_id)
      : listContestCellAccepted(contestId.value, row.user_id, cell.problem_id))
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
      router.push(`${contextBase.value}/submissions/${row.id}`)
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
        // 封榜期间提交：灰色问号，保持结果悬念
        return h(
          'span',
          { class: 'cell-pill cell-pill--frozen', title: t('contests.board.frozenCellHint') },
          '?',
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
      const acCls = isFirstSolve(c) ? 'cell-pill--first' : 'cell-pill--ac'
      if (isAcM.value) {
        if (c.accepted)
          return pill(acCls, String(c.penalty), boardClickable.value ? open : undefined)
        if (c.attempts > 0) return pill('cell-pill--try', `-${c.attempts}`)
        return pill('cell-pill--idle', '·')
      }
      if (c.accepted) return pill(acCls, String(c.score), boardClickable.value ? open : undefined)
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

// ---- 榜单工具栏：昵称关键字过滤（榜单整表随请求返回，纯客户端过滤）+ 受控分页 ----
const boardKeyword = ref('')
const boardPagination = reactive({ page: 1, pageSize: 20 })

const filteredBoardRows = computed<Row[]>(() => {
  const kw = boardKeyword.value.trim().toLowerCase()
  if (!kw) return boardRows.value
  return boardRows.value.filter((r) => r.nickname.toLowerCase().includes(kw))
})

function onBoardSearch() {
  boardPagination.page = 1
}

/** 榜单当前页数据（客户端分页） */
const pagedBoardRows = computed<Row[]>(() => {
  const start = (boardPagination.page - 1) * boardPagination.pageSize
  return filteredBoardRows.value.slice(start, start + boardPagination.pageSize)
})

function onBoardPage(page: number) {
  boardPagination.page = page
}
</script>

<template>
  <SearchFilterBar
    :keyword="boardKeyword"
    :placeholder="t('contests.board.search')"
    @update:keyword="
      (v: string) => {
        boardKeyword = v
      }
    "
    @search="onBoardSearch"
    @reset="onBoardSearch"
  >
    <template #actions>
      <RefreshButton
        :loading="boardLoading"
        :aria-label="t('action.refresh')"
        @click="loadBoard()"
      />
    </template>
  </SearchFilterBar>
  <n-alert v-if="detail.board_frozen" type="warning" :bordered="false" class="frozen-hint">
    {{ t('contests.frozenHint') }}
  </n-alert>
  <PaginatedDataTable
    :columns="boardColumns"
    :data="pagedBoardRows"
    :loading="boardLoading"
    :total="filteredBoardRows.length"
    :page="boardPagination.page"
    :page-size="boardPagination.pageSize"
    :empty-text="t('contests.board.empty')"
    :table-props="{ class: 'board-table', scrollX: 1000, flexHeight: true }"
    @update:page="onBoardPage"
  >
    <template #pager-left>
      <span class="pager__total">
        {{ t('contests.board.totalCount', { count: filteredBoardRows.length }) }}
      </span>
    </template>
  </PaginatedDataTable>

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
</template>

<style scoped>
/* 榜单：flex-height 表格撑满剩余高度（表体内部滚动），分页条贴底 */
.board-table {
  flex: 1;
  min-height: 0;
}
.frozen-hint {
  flex-shrink: 0;
}

/* ---- 榜单：双行题头 + 药丸格（色值均由设计令牌 color-mix 派生）。
   格内 DOM 由列 render 的 h() 在 naive-ui 内部创建、不带本组件 scoped 属性，
   故全部样式经 .board-table :deep() 下穿（同 solveMark.ts 的已知约束）。 ---- */
.board-table :deep(.cell-head) {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  line-height: 1.2;
}
.board-table :deep(.cell-head__letter) {
  font-weight: 650;
}
.board-table :deep(.cell-head__score) {
  font-size: 11px;
  font-weight: 500;
  color: var(--app-text-secondary);
}
.board-table :deep(.solved-cell) {
  font-variant-numeric: tabular-nums;
  color: var(--app-text-secondary);
}
.board-table :deep(.cell-pill) {
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
.board-table :deep(.cell-pill--ac) {
  background: color-mix(in srgb, var(--app-success, #18a058) 14%, transparent);
  color: var(--app-success, #18a058);
}
/* 全场首次通过（一血）：实心深绿 + 白字 */
.board-table :deep(.cell-pill--first) {
  background: var(--app-success, #18a058);
  color: #fff;
}
.board-table :deep(.cell-pill--part) {
  background: color-mix(in srgb, var(--app-info, #2080f0) 12%, transparent);
  color: var(--app-info, #2080f0);
}
.board-table :deep(.cell-pill--try) {
  background: color-mix(in srgb, var(--app-error, #d03050) 12%, transparent);
  color: var(--app-error, #d03050);
  font-weight: 600;
}
/* 封榜期间提交：灰色虚线格，隐藏结果保持悬念 */
.board-table :deep(.cell-pill--frozen) {
  background: var(--app-muted-bg);
  color: var(--app-text-secondary);
  border: 1px dashed var(--app-border);
  padding: 1px 9px;
  font-weight: 650;
}
.board-table :deep(.cell-pill--idle) {
  color: var(--app-text-secondary);
  opacity: 0.5;
  font-weight: 500;
}
.board-table :deep(.cell-pill--link) {
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
.board-table :deep(.cell-pill--link:hover) {
  filter: brightness(1.05);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--app-success, #18a058) 35%, transparent);
}
</style>
