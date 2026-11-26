<script setup lang="ts">
import { computed, h, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { getContestBoard, listContestCellAccepted } from '@/api/contests'
import { getTeamContestBoard, listTeamContestCellAccepted } from '@/api/teams'
import PaginatedTable from '@/components/common/PaginatedTable.vue'
import RefreshButton from '@/components/common/RefreshButton.vue'
import InlineNotice from '@/components/common/InlineNotice.vue'
import SearchFilterBar from '@/components/common/SearchFilterBar.vue'
import type { AppTableColumn } from '@/components/common/table-types'
import { useUserStore } from '@/stores/user'
import { message } from '@/utils/feedback'
import BoardCell from './BoardCell.vue'
import CellSubmissionsDialog from './CellSubmissionsDialog.vue'
import type {
  Board,
  BoardCell as BoardCellData,
  ContestDetail,
  ContestSubmissionItem,
} from '@/types'

const props = defineProps<{
  detail: ContestDetail
  teamId: string | null
  contextBase: string
  active: boolean
  pageActive: boolean
  /** 报名等操作后由父级自增，触发静默重拉榜单 */
  refreshToken: number
}>()

const router = useRouter()
const { t } = useI18n()
const userStore = useUserStore()

const BOARD_PAGE_SIZE = 20
/** 进行中榜单轮询间隔：须小于后端读缓存 TTL（当前 20s），让轮询命中缓存 */
const POLL_INTERVAL_MS = 15000

const board = ref<Board | null>(null)
const loading = ref(false)
const loaded = ref(false)
const keyword = ref('')
const page = ref(1)
let pollTimer: number | null = null

const isAcm = computed(() => board.value?.rule_type === 'ACM')

/** 每题全场首次 AC 的时间戳（一血判定；封榜格不参与，避免提前揭晓） */
const firstAcceptedAt = computed<Record<string, number>>(() => {
  const map: Record<string, number> = {}
  if (!board.value) return map
  for (const row of board.value.rows) {
    for (const cell of row.cells) {
      if (!cell.accepted || !cell.accepted_at || cell.is_frozen) continue
      const ts = Date.parse(cell.accepted_at)
      if (Number.isNaN(ts)) continue
      const current = map[cell.problem_id]
      if (current === undefined || ts < current) map[cell.problem_id] = ts
    }
  }
  return map
})

function isFirstSolve(cell: BoardCellData): boolean {
  if (!cell.accepted || !cell.accepted_at || cell.is_frozen) return false
  const ts = Date.parse(cell.accepted_at)
  if (Number.isNaN(ts)) return false
  const first = firstAcceptedAt.value[cell.problem_id]
  return first !== undefined && ts === first
}

interface BoardRowView {
  rank: number
  user_id: string
  nickname: string
  solved: number
  metric: number
  cells: BoardCellData[]
}

/** 榜单 AC 格可点：与提交记录同一窗口与角色门控（封榜格子保持冻结态，不可点） */
const canViewSubmissions = computed(() => {
  const detail = props.detail
  if (detail.can_manage) return true
  return userStore.isLoggedIn && Date.now() >= new Date(detail.end_time).getTime()
})

const rows = computed<BoardRowView[]>(() => {
  if (!board.value) return []
  return board.value.rows.map((row) => ({
    rank: row.rank,
    user_id: row.user_id,
    nickname: row.nickname,
    solved: row.solved,
    metric: isAcm.value ? row.total_penalty : row.total_score,
    cells: row.cells,
  }))
})

const filteredRows = computed<BoardRowView[]>(() => {
  const needle = keyword.value.trim().toLowerCase()
  if (!needle) return rows.value
  return rows.value.filter((row) => row.nickname.toLowerCase().includes(needle))
})

const pagedRows = computed<BoardRowView[]>(() => {
  const start = (page.value - 1) * BOARD_PAGE_SIZE
  return filteredRows.value.slice(start, start + BOARD_PAGE_SIZE)
})

const columns = computed<AppTableColumn<BoardRowView>[]>(() => {
  const headerCells = board.value?.rows[0]?.cells ?? []
  const list: AppTableColumn<BoardRowView>[] = [
    {
      key: 'rank',
      title: t('contests.board.rank'),
      width: '64px',
      align: 'center',
      cell: (row) => String(row.rank),
      cellClass: 'tabular-nums text-muted-foreground',
    },
    {
      key: 'user',
      title: t('contests.board.user'),
      width: '170px',
      cell: (row) => h('span', { class: 'font-medium' }, row.nickname),
    },
    {
      key: 'solved',
      title: t('contests.board.solved'),
      width: '92px',
      align: 'center',
      cell: (row) =>
        h(
          'span',
          { class: 'tabular-nums text-muted-foreground' },
          `${row.solved}/${row.cells.length}`,
        ),
    },
    {
      key: 'metric',
      title: isAcm.value ? t('contests.board.penalty') : t('contests.board.totalScore'),
      width: '88px',
      align: 'right',
      cell: (row) => String(row.metric),
      cellClass: 'tabular-nums font-medium',
    },
  ]
  headerCells.forEach((cell, index) => {
    const letter = cell.letter ?? String(index + 1)
    const title =
      !isAcm.value && cell.problem_score > 0 ? `${letter} · ${cell.problem_score}` : letter
    list.push({
      key: `cell-${cell.problem_id}`,
      title,
      width: '84px',
      align: 'center',
      cell: (row) => {
        const target = row.cells[index]
        if (!target) return h('span', { class: 'text-muted-foreground/50' }, '·')
        return h(BoardCell, {
          cell: target,
          acm: isAcm.value,
          first: isFirstSolve(target),
          clickable: canViewSubmissions.value,
          onOpen: () => void openCell(row, target),
        })
      },
    })
  })
  return list
})

const cellModal = reactive({
  open: false,
  loading: false,
  title: '',
  items: [] as ContestSubmissionItem[],
})

async function openCell(row: BoardRowView, cell: BoardCellData): Promise<void> {
  if (!canViewSubmissions.value) return
  cellModal.open = true
  cellModal.loading = true
  cellModal.title = `${cell.letter ?? ''} · ${row.nickname}`
  cellModal.items = []
  try {
    cellModal.items = await (props.teamId
      ? listTeamContestCellAccepted(props.teamId, props.detail.id, row.user_id, cell.problem_id)
      : listContestCellAccepted(props.detail.id, row.user_id, cell.problem_id))
  } catch (error) {
    cellModal.open = false
    message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    cellModal.loading = false
  }
}

function openSubmission(item: ContestSubmissionItem): void {
  cellModal.open = false
  void router.push(`${props.contextBase}/submissions/${item.id}`)
}

async function loadBoard(silent = false): Promise<void> {
  loading.value = !silent
  try {
    board.value = await (props.teamId
      ? getTeamContestBoard(props.teamId, props.detail.id)
      : getContestBoard(props.detail.id))
    loaded.value = true
    syncPolling()
  } catch (error) {
    if (!silent) message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    loading.value = false
  }
}

function shouldPoll(): boolean {
  return (
    props.active &&
    props.pageActive &&
    loaded.value &&
    props.detail.status === 'running' &&
    !props.detail.board_frozen
  )
}

function stopPolling(): void {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

function syncPolling(): void {
  if (!shouldPoll()) {
    stopPolling()
    return
  }
  if (pollTimer === null) {
    pollTimer = window.setInterval(() => void loadBoard(true), POLL_INTERVAL_MS)
  }
}

function onSearch(): void {
  page.value = 1
}

watch(
  [() => props.active, () => props.pageActive],
  () => {
    if (props.active && props.pageActive && !loaded.value) {
      void loadBoard()
      return
    }
    syncPolling()
  },
  { immediate: true },
)

watch(() => [props.detail.status, props.detail.board_frozen], syncPolling)

watch(
  () => props.refreshToken,
  () => {
    if (loaded.value) void loadBoard(true)
  },
)

onBeforeUnmount(stopPolling)
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col gap-2.5">
    <SearchFilterBar
      :keyword="keyword"
      :placeholder="t('contests.board.search')"
      @update:keyword="keyword = $event"
      @search="onSearch"
      @reset="onSearch"
    >
      <template #actions>
        <RefreshButton :loading="loading" :label="t('action.refresh')" @click="loadBoard()" />
      </template>
    </SearchFilterBar>

    <InlineNotice v-if="detail.board_frozen" tone="warning">
      {{ t('contests.frozenHint') }}
    </InlineNotice>

    <PaginatedTable
      :columns="columns"
      :data="pagedRows"
      :loading="loading"
      :total="filteredRows.length"
      :page="page"
      :page-size="BOARD_PAGE_SIZE"
      :empty-text="t('contests.board.empty')"
      @update:page="page = $event"
    >
      <template #pager-left>
        <span class="tabular-nums">
          {{ t('contests.board.totalCount', { count: filteredRows.length }) }}
        </span>
      </template>
    </PaginatedTable>

    <CellSubmissionsDialog
      v-model:open="cellModal.open"
      :loading="cellModal.loading"
      :title="cellModal.title"
      :items="cellModal.items"
      @open-submission="openSubmission"
    />
  </div>
</template>
