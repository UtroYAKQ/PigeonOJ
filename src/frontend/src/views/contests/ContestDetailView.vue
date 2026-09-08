<script setup lang="ts">
/**
 * 比赛详情：主页（hero + 倒计时条 + 数据瓦片 + 时间轴 + 说明）/ 题目 / 榜单 / 提交记录 四个 tab。
 * 题目进入比赛上下文写题页（统一入口交题）；榜单封榜展示冻结快照，
 * 解冻为 admin/tutor 手动操作（重算回填封榜期结果）；进行中榜单 15s 轮询。
 * 提交记录比赛期间仅管理角色（can_manage）可见，赛后对所有登录用户开放（行点击进上下文内评测结果页）。
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
import { MoreFilled } from '@element-plus/icons-vue'
import type { DataTableColumns, DropdownOption } from 'naive-ui'

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
} from '@/api/contests'
import {
  getTeamContest,
  getTeamContestBoard,
  listTeamContestCellAccepted,
  listTeamContestSubmissions,
  registerTeamContest,
} from '@/api/teams'
import { message } from '@/utils/feedback'
import { formatDateTime } from '@/utils/format'
import { renderSolveMark } from '@/utils/solveMark'
import { usePagination } from '@/composables/usePagination'
import { useUserStore } from '@/stores/user'
import SearchFilterBar from '@/components/SearchFilterBar.vue'
import { languageOptions } from '@/constants/languages'
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
const userStore = useUserStore()

const loading = ref(false)
const detail = ref<ContestDetail | null>(null)
const registering = ref(false)
type ContestTab = 'home' | 'problems' | 'board' | 'submissions'
const TAB_KEYS: ContestTab[] = ['home', 'problems', 'board', 'submissions']
function tabFromQuery(raw: unknown): ContestTab {
  const value = typeof raw === 'string' ? raw : ''
  return (TAB_KEYS as string[]).includes(value) ? (value as ContestTab) : 'home'
}
const activeTab = ref<ContestTab>(tabFromQuery(route.query.tab))

/** 比赛 id：全局路由取 params.id，团队上下文路由取 params.cid */
const contestId = computed(() => String(route.params.cid ?? route.params.id))
const teamId = computed(() => (route.params.teamId ? String(route.params.teamId) : null))
/** 上下文基路径（frontend.md 路由上下文隔离）：团队比赛路由内导航不跳出团队前缀 */
const contextBase = computed(() =>
  teamId.value
    ? `/teams/${teamId.value}/contests/${contestId.value}`
    : `/contests/${contestId.value}`,
)

// ---- 提交记录（tab 激活时懒加载；比赛期间仅管理角色可见，赛后对所有登录用户开放） ----
const submissions = ref<ContestSubmissionItem[]>([])
const subsLoading = ref(false)
const {
  page: subsPage,
  pageSize: subsPageSize,
  total: subsTotal,
  changePage,
  changeSize,
  resetPage: subsResetPage,
  beginLoad: subsBeginLoad,
  isCurrent: subsIsCurrent,
} = usePagination()

/** 提交记录筛选条件（昵称关键字 / 语言 / 题目 / 状态，均随请求透传）；
 * 下拉筛选以 null 表示不限——naive-ui n-select 对 '' 会走 fallback 渲染成空串，
 * placeholder（「全部题目」等文字提示）只在 null 时展示 */
const subsQuery = reactive({
  keyword: '',
  language: null as string | null,
  problemId: null as string | null,
  status: null as string | null,
})

/** 比赛期间（end_time 之前）提交记录对参赛者隐藏；管理角色（admin/tutor）随时可见 */
const subsLocked = computed(
  () =>
    !!detail.value &&
    !detail.value.can_manage &&
    Date.now() < new Date(detail.value.end_time).getTime(),
)
/** 赛后向所有登录用户开放（含未报名者）；管理角色随时可见 */
const subsAllowed = computed(() => {
  const d = detail.value
  return (
    !!d && (d.can_manage || (userStore.isLoggedIn && Date.now() >= new Date(d.end_time).getTime()))
  )
})

async function loadSubmissions(silent = false) {
  const seq = subsBeginLoad()
  subsLoading.value = !silent
  try {
    const query = {
      page: subsPage.value,
      page_size: subsPageSize.value,
      keyword: subsQuery.keyword || undefined,
      language: subsQuery.language || undefined,
      problem_id: subsQuery.problemId || undefined,
      status: subsQuery.status || undefined,
    }
    const result = await (teamId.value
      ? listTeamContestSubmissions(teamId.value, contestId.value, query)
      : listContestSubmissions(contestId.value, query))
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

/** 筛选条件变更：回第一页重新加载 */
function onSubsSearch() {
  subsResetPage()
  void loadSubmissions()
}

/** 题目筛选选项（比赛题目，题号 + 标题；详情携带题目时才可筛选） */
const subsProblemOptions = computed(() =>
  (detail.value?.problems ?? []).map((p) => ({
    value: p.problem_id,
    label: p.letter ? `${p.letter} · ${p.title}` : p.title,
  })),
)

/** 语言筛选选项（复用判题语言字典；空值「全部语言」由 clearable placeholder 承担） */
const subsLanguageOptions = languageOptions.map((option) => ({
  label: option.label,
  value: option.value,
}))

/** 状态筛选选项（常用结果；标签复用 problems.status 字典） */
const subsStatusOptions = [
  { value: 'accepted', labelKey: 'problems.status.accepted' },
  { value: 'wrong_answer', labelKey: 'problems.status.wrong_answer' },
  { value: 'compile_error', labelKey: 'problems.status.compile_error' },
].map((option) => ({ value: option.value, label: t(option.labelKey) }))

function changeSubsPage(value: number) {
  changePage(value)
  void loadSubmissions()
}

function changeSubsPageSize(value: number) {
  changeSize(value)
  void loadSubmissions()
}

function openSubmission(row: ContestSubmissionItem) {
  router.push(`${contextBase.value}/submissions/${row.id}`)
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
    detail.value = await (teamId.value
      ? getTeamContest(teamId.value, contestId.value)
      : getContest(contestId.value))
  } catch (error) {
    if (!silent) message.error(error instanceof Error ? error.message : t('common.loadFailed'))
  } finally {
    if (!silent) loading.value = false
  }
}

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

watch(
  () => route.query.tab,
  (raw) => {
    const next = tabFromQuery(raw)
    if (next !== activeTab.value) activeTab.value = next
  },
)

function stopPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

function startTimers() {
  if (clockTimer !== null || pollTimer !== null) return // 已在运行（如 activated 重复触发）
  clockTimer = window.setInterval(() => {
    nowTick.value = Date.now()
  }, 1_000)
  // 进行中榜单 15s 轮询；须 < 后端 BOARD_CACHE_TTL_RUNNING（contest.py，当前 20s），
  // 使轮询命中读缓存而非每次回源重算（改此值需同步后端 TTL）
  pollTimer = window.setInterval(() => {
    if (
      activeTab.value === 'board' &&
      detail.value?.status === 'running' &&
      !detail.value.board_frozen
    ) {
      void loadBoard(true)
    }
  }, 15000)
}

onMounted(() => {
  void load()
  startTimers()
})
// KeepAlive 缓存页：被切走时停表（后台不空转），返回时恢复
onDeactivated(() => {
  stopPolling()
  if (clockTimer !== null) {
    window.clearInterval(clockTimer)
    clockTimer = null
  }
})
onActivated(() => {
  // keepAlive 返回：重拉详情（编排题目后返回不显示旧空数据），恢复计时器
  if (detail.value) void load()
  startTimers()
})
onBeforeUnmount(() => {
  stopPolling()
  if (clockTimer !== null) {
    window.clearInterval(clockTimer)
    clockTimer = null
  }
})

async function register() {
  if (!detail.value) return
  registering.value = true
  try {
    await (teamId.value
      ? registerTeamContest(teamId.value, detail.value.id)
      : registerContest(detail.value.id))
    message.success(t('common.success'))
    await load(true)
    if (activeTab.value === 'board') void loadBoard(true)
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('common.operationFailed'))
  } finally {
    registering.value = false
  }
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

const manageOptions = computed<DropdownOption[]>(() => {
  if (!detail.value?.can_manage) return []
  return [
    {
      key: 'edit',
      label: t('contests.detail.manage'),
      disabled: detail.value.status !== 'scheduled',
    },
    { key: 'tools', label: t('contests.tools.title') },
  ]
})

function onManageSelect(key: string | number) {
  const cid = contestId.value
  const team = teamId.value
  if (key === 'edit') {
    if (detail.value?.status !== 'scheduled') return
    void router.push(
      team ? `/teams/${team}/contests/${cid}/edit/basic` : `/admin/contests/${cid}/edit/basic`,
    )
    return
  }
  if (key === 'tools') {
    void router.push(team ? `/teams/${team}/contests/${cid}/tools` : `/admin/contests/${cid}/tools`)
  }
}

// ---------------- 主页：时钟与倒计时 ----------------

/** 每秒自增的"当前时间"（驱动翻页时钟倒计时，不重拉数据） */
const nowTick = ref(Date.now())
let clockTimer: number | null = null

/** 毫秒 → 翻页时钟分段（天:时:分:秒，零填充） */
function toSegments(ms: number): { value: string; unit: string }[] {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const days = Math.floor(totalSeconds / 86400)
  const hours = Math.floor((totalSeconds % 86400) / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return [
    { value: pad(days), unit: t('contests.detail.unitDay') },
    { value: pad(hours), unit: t('contests.detail.unitHour') },
    { value: pad(minutes), unit: t('contests.detail.unitMinute') },
    { value: pad(seconds), unit: t('contests.detail.unitSecond') },
  ]
}

/** Hero 翻页时钟：未开始 → 距开始；进行中 → 距结束；结束 → null（恒定文案） */
const digitalCountdown = computed(() => {
  const d = detail.value
  if (!d) return null
  const now = nowTick.value
  const start = new Date(d.start_time).getTime()
  const end = new Date(d.end_time).getTime()
  if (d.status === 'running') {
    return { label: t('contests.detail.endsIn'), segments: toSegments(end - now) }
  }
  if (d.status === 'finished' || now >= end) {
    return null
  }
  return { label: t('contests.detail.startsIn'), segments: toSegments(start - now) }
})

// ---------------- 题目列表 ----------------

const problemColumns = computed<DataTableColumns<ContestProblemItem>>(() => [
  {
    // 本人在该场比赛的作答状态（练习 / 验题通过不计入）；悬停查看语义
    title: '',
    key: 'solved',
    width: 72,
    render: (row) => renderSolveMark(t, row.solved),
  },
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
  // ACM 赛制无 IOI 单题分语义（按通过 / 罚时计），分数列仅 IOI 展示
  ...(detail.value?.rule_type === 'IOI'
    ? [
        {
          title: t('contests.list.problemScore'),
          key: 'score',
          width: 100,
          render: (row: ContestProblemItem) => (row.score > 0 ? String(row.score) : '--'),
        },
      ]
    : []),
])

function goProblem(row: ContestProblemItem) {
  if (!detail.value) return
  router.push(`${contextBase.value}/problems/${row.problem_id}`)
}

function problemRowProps(row: ContestProblemItem) {
  return {
    style: 'cursor: pointer;',
    onClick: () => goProblem(row),
  }
}

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

function onBoardPageSize(pageSize: number) {
  boardPagination.pageSize = pageSize
  boardPagination.page = 1
}

// ---------------- 提交记录 ----------------

const submissionColumns = computed<DataTableColumns<ContestSubmissionItem>>(() => {
  // ACM 二值分（AC=满分否则 0）不是部分分，提交记录不展示分数列（IOI 才有意义）
  const cols: DataTableColumns<ContestSubmissionItem> = [
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
  ]
  if (detail.value?.rule_type !== 'ACM') {
    cols.push({
      title: t('problems.submission.score'),
      key: 'score',
      width: 80,
      render: (row) => row.score ?? '-',
    })
  }
  cols.push(
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
  )
  return cols
})
</script>

<template>
  <WorkbenchShell>
    <div class="contest-fill">
      <!-- 加载骨架 / 失败态：背景板位置占位（团队页同款，不把内容包进 n-spin） -->
      <div v-if="!detail" class="hero" :class="loading ? 'hero--skeleton' : 'hero--failed'">
        <div v-if="loading" class="hero-skeleton">
          <n-skeleton height="64px" width="64px" :sharp="false" round />
          <div class="hero-skeleton__lines">
            <n-skeleton text style="width: 32%" />
            <n-skeleton text style="width: 58%" />
          </div>
        </div>
        <n-empty v-else :description="t('common.loadFailed')" size="large">
          <template #extra>
            <n-button @click="load()">{{ t('action.refresh') }}</n-button>
          </template>
        </n-empty>
      </div>

      <template v-else>
        <!-- ======== Hero 背景板（团队页同款：中性底 + 主色几何点缀） ======== -->
        <section class="hero">
          <div class="hero__banner" aria-hidden="true">
            <span class="hero__orb"></span>
            <span class="hero__ring"></span>
          </div>
          <div class="hero__body">
            <div class="hero__row hero__row--top">
              <div class="hero__logo">
                <img v-if="detail.logo" :src="detail.logo" alt="logo" />
                <span v-else>{{ initial }}</span>
              </div>
              <div class="hero__id">
                <h1 class="hero__title">{{ detail.title }}</h1>
                <div class="hero__chips">
                  <span class="hero__chip" :class="`hero__chip--${statusMeta.type}`">
                    <span
                      v-if="detail.status === 'running'"
                      class="hero__pulse"
                      aria-hidden="true"
                    ></span>
                    {{ statusMeta.label }}
                  </span>
                  <span class="hero__chip">{{ detail.rule_type }}</span>
                  <span
                    v-if="detail.my_registration === 'registered'"
                    class="hero__chip hero__chip--ok"
                  >
                    {{ t('contests.detail.registered') }}
                  </span>
                  <span v-if="detail.board_frozen" class="hero__chip hero__chip--warning">
                    {{ t('contests.boardFrozenTag') }}
                  </span>
                </div>
                <!-- 统计行：题目数 / 报名数（标题正下方） -->
                <div class="hero__meta">
                  <span>
                    {{ t('contests.detail.problems') }}
                    <strong class="hero__meta-num">{{ detail.problem_count }}</strong>
                  </span>
                  <span class="hero__dot" aria-hidden="true">·</span>
                  <span>
                    {{ t('contests.detail.registeredCount') }}
                    <strong class="hero__meta-num">{{ detail.registered_count }}</strong>
                  </span>
                </div>
              </div>
              <!-- 动作区：翻页时钟（未开始 → 距开始；进行中 → 距结束）+ 报名 -->
              <div class="hero__actions">
                <div
                  v-if="digitalCountdown"
                  class="hero__clock"
                  :class="`hero__clock--${detail.status}`"
                >
                  <span class="hero__clock-label">{{ digitalCountdown.label }}</span>
                  <div
                    class="flip-clock"
                    :aria-label="`${digitalCountdown.label} ${digitalCountdown.segments
                      .map((s) => s.value)
                      .join(':')}`"
                  >
                    <template v-for="(seg, gi) in digitalCountdown.segments" :key="gi">
                      <span v-if="gi > 0" class="flip-clock__colon" aria-hidden="true">:</span>
                      <span class="flip-clock__group">
                        <span
                          v-for="(ch, ci) in seg.value"
                          :key="`${gi}-${ci}-${ch}`"
                          class="flip-clock__card"
                          >{{ ch }}</span
                        >
                      </span>
                    </template>
                  </div>
                </div>
                <span v-else class="hero__clock-label">{{ t('contests.detail.contestOver') }}</span>
                <n-button
                  v-if="detail.can_register"
                  type="primary"
                  size="large"
                  :loading="registering"
                  @click="register"
                >
                  {{ t('contests.detail.register') }}
                </n-button>
                <n-dropdown
                  v-if="manageOptions.length"
                  trigger="click"
                  placement="bottom-end"
                  :options="manageOptions"
                  @select="onManageSelect"
                >
                  <n-button circle quaternary size="large" :aria-label="t('teams.detail.more')">
                    <template #icon>
                      <n-icon :component="MoreFilled" />
                    </template>
                  </n-button>
                </n-dropdown>
              </div>
            </div>
          </div>
        </section>

        <!-- ======== 内容模块（tab 线条直连内容） ========
             display-directive="show"：pane 挂载后常驻（仅 display 切换），
             避免 if 模式反复卸载重建在 v-show 互斥节点上引发补丁错位（内容丢失） -->
        <section class="module-area">
          <n-tabs type="line" v-model:value="activeTab" class="module-tabs">
            <!-- ======== 主页 ======== -->
            <n-tab-pane name="home" :tab="t('contests.detail.tabHome')" display-directive="show">
              <div class="pane-scroll">
                <!-- 公告条：赛时可由管理角色更新（Markdown） -->
                <n-alert
                  v-if="detail.announcement"
                  type="info"
                  :bordered="false"
                  class="announcement"
                >
                  <template #header>
                    <div class="announcement__head">
                      <span>{{ t('contests.detail.announcement') }}</span>
                      <span v-if="detail.announcement_updated_at" class="announcement__time">
                        {{ t('contests.detail.announcementUpdatedAt') }}
                        {{ formatDateTime(detail.announcement_updated_at) }}
                      </span>
                    </div>
                  </template>
                  <MarkdownView :source="detail.announcement" />
                </n-alert>
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
            <n-tab-pane
              name="problems"
              :tab="t('contests.detail.tabProblems')"
              display-directive="show"
            >
              <div class="pane-scroll">
                <n-alert v-if="!detail.can_view_problems" type="info" :bordered="false">
                  {{ t('contests.detail.notVisible') }}
                </n-alert>
                <!-- 空态样板（frontend.md）：与内容区 v-show 互斥切换，空态用全局
                     table-fill-empty 在 tab 纵向剩余空间内拉伸居中 -->
                <n-data-table
                  v-show="detail.can_view_problems && detail.problems.length"
                  :columns="problemColumns"
                  :data="detail.problems"
                  :bordered="false"
                  :bottom-bordered="false"
                  :row-props="problemRowProps"
                />
                <div
                  v-show="detail.can_view_problems && !detail.problems.length"
                  class="table-fill-empty detail-empty"
                >
                  <n-empty size="large" :description="t('contests.list.problemsEmpty')" />
                </div>
              </div>
            </n-tab-pane>

            <!-- ======== 榜单 ======== -->
            <n-tab-pane name="board" :tab="t('contests.detail.tabBoard')" display-directive="show">
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
              <n-alert
                v-if="detail.board_frozen"
                type="warning"
                :bordered="false"
                class="frozen-hint"
              >
                {{ t('contests.frozenHint') }}
              </n-alert>
              <n-data-table
                v-show="filteredBoardRows.length"
                class="board-table"
                :columns="boardColumns"
                :data="pagedBoardRows"
                :loading="boardLoading"
                :bordered="false"
                :bottom-bordered="false"
                :scroll-x="1000"
                flex-height
              />
              <div v-show="!filteredBoardRows.length" class="table-fill-empty detail-empty">
                <n-empty size="large" :description="t('contests.board.empty')" />
              </div>
              <div class="board-pager">
                <span class="pager__total">
                  {{ t('contests.board.totalCount', { count: filteredBoardRows.length }) }}
                </span>
                <n-pagination
                  :page="boardPagination.page"
                  :page-size="boardPagination.pageSize"
                  :item-count="filteredBoardRows.length"
                  :page-sizes="[10, 20, 50]"
                  show-size-picker
                  @update:page="onBoardPage"
                  @update:page-size="onBoardPageSize"
                />
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
            <n-tab-pane
              name="submissions"
              :tab="t('contests.detail.tabSubmissions')"
              display-directive="show"
            >
              <n-alert v-if="subsLocked" type="info" :bordered="false" class="subs-hint">
                {{ t('contests.submissions.hiddenDuringContest') }}
              </n-alert>
              <n-alert v-else-if="!subsAllowed" type="info" :bordered="false" class="subs-hint">
                {{ t('contests.submissions.loginRequired') }}
              </n-alert>
              <template v-else>
                <SearchFilterBar
                  :keyword="subsQuery.keyword"
                  :placeholder="t('contests.submissions.search')"
                  @update:keyword="
                    (v: string) => {
                      subsQuery.keyword = v
                    }
                  "
                  @search="onSubsSearch"
                  @reset="onSubsSearch"
                >
                  <n-select
                    v-model:value="subsQuery.problemId"
                    clearable
                    filterable
                    style="width: 200px"
                    :options="subsProblemOptions"
                    :placeholder="t('contests.submissions.allProblems')"
                    @update:value="onSubsSearch"
                  />
                  <n-select
                    v-model:value="subsQuery.language"
                    clearable
                    style="width: 150px"
                    :options="subsLanguageOptions"
                    :placeholder="t('contests.submissions.allLanguages')"
                    @update:value="onSubsSearch"
                  />
                  <n-select
                    v-model:value="subsQuery.status"
                    clearable
                    style="width: 130px"
                    :options="subsStatusOptions"
                    :placeholder="t('common.allStatus')"
                    @update:value="onSubsSearch"
                  />
                </SearchFilterBar>
                <PaginatedDataTable
                  :columns="submissionColumns"
                  :data="submissions"
                  :loading="subsLoading"
                  :total="subsTotal"
                  v-model:page="subsPage"
                  v-model:page-size="subsPageSize"
                  :page-sizes="[20, 50, 100]"
                  :empty-text="t('contests.submissions.empty')"
                  :table-props="{ scrollX: 900, flexHeight: true, rowProps: submissionRowProps }"
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
        </section>
      </template>
    </div>
  </WorkbenchShell>
</template>

<style scoped>
/* ---- 通栏填充 + 一屏锁定：卡片内容 → 填充区 → 模块区 → tabs → pane 纵向伸展，
     表格区（table-fill / flex-height）撑满剩余高度、表体内部滚动，分页条恒贴底 ---- */
/* 通栏填充：抵消应用壳卡片默认 padding，Hero 背景板直接铺到卡片边缘 */
.contest-fill {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  margin: calc(-1 * var(--n-padding-top, 20px)) calc(-1 * var(--n-padding-left, 24px))
    calc(-1 * var(--n-padding-bottom, 24px));
}

/* 加载骨架 / 失败态：占位在背景板位置 */
.hero--skeleton {
  padding: 28px 32px;
}
.hero-skeleton {
  display: flex;
  align-items: center;
  gap: 16px;
}
.hero-skeleton__lines {
  flex: 1;
  display: grid;
  gap: 8px;
  max-width: 420px;
}
.hero--failed {
  padding: 56px 32px;
  display: flex;
  justify-content: center;
}

/* ======== Hero 背景板：中性底 + 主色几何（团队页同款规则） ========
   底色比卡片深一档（surface-muted），主色只以「被裁切的圆」出现：
   右上实心巨弧 + 右下描边环，画面内不留完整圆形。 */
.hero {
  position: relative;
  flex-shrink: 0;
  border-bottom: 1px solid var(--app-border);
  background:
    radial-gradient(
      90% 220% at 97% 112%,
      color-mix(in srgb, var(--app-primary) 6%, transparent) 0%,
      transparent 62%
    ),
    radial-gradient(
      120% 180% at 0% 0%,
      color-mix(in srgb, var(--app-primary) 5%, transparent) 0%,
      transparent 52%
    ),
    var(--app-surface-muted, #f7f7fa);
  overflow: hidden;
}
/* 巨圆：圆心落在上沿外 252px，只露出底部一弧；
   填充用径向渐变（20% → 5% → 0），边缘化开，避免出现生硬的色块边界 */
.hero__orb {
  position: absolute;
  width: 340px;
  height: 340px;
  border-radius: 999px;
  right: 7%;
  top: -252px;
  background: radial-gradient(
    circle at 50% 50%,
    color-mix(in srgb, var(--app-primary) 20%, transparent) 0%,
    color-mix(in srgb, var(--app-primary) 5%, transparent) 58%,
    transparent 74%
  );
}
/* 描边环：被右侧与底部各裁一截，与上方实心弧形成一虚一实 */
.hero__ring {
  position: absolute;
  width: 228px;
  height: 228px;
  border-radius: 999px;
  right: -104px;
  bottom: -120px;
  border: 1px solid color-mix(in srgb, var(--app-primary) 24%, transparent);
}
.hero__body {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 26px 32px 20px;
  max-width: 1680px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}
/* 第一行：logo + 标题/标签/统计 + 翻页时钟/报名动作区 */
.hero__row--top {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
/* 比赛Logo：团队头像同款尺寸与描边 */
.hero__logo {
  width: 88px;
  height: 88px;
  border-radius: 10px;
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--app-card-bg, #fff);
  border: 3px solid var(--app-card-bg, #fff);
  box-shadow: 0 2px 12px rgb(0 0 0 / 8%);
  font-size: 32px;
  font-weight: 800;
  color: var(--app-text-secondary);
}
.hero__logo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.hero__id {
  flex: 1;
  min-width: 240px;
  display: grid;
  gap: 8px;
}
.hero__title {
  margin: 0;
  line-height: 1.2;
  font-size: 22px;
  font-weight: 700;
  color: var(--app-text);
  margin-right: 4px;
}
.hero__chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
/* 标签：直角矩形（不用圆角药丸） */
.hero__chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px;
  border-radius: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--app-text-secondary);
  background: var(--app-card-bg, #fff);
  border: 1px solid var(--app-border);
}
.hero__chip--success {
  color: var(--app-success, #18a058);
  border-color: color-mix(in srgb, var(--app-success, #18a058) 45%, transparent);
  background: color-mix(in srgb, var(--app-success, #18a058) 8%, var(--app-card-bg, #fff));
}
.hero__chip--info {
  color: var(--app-info, #2080f0);
  border-color: color-mix(in srgb, var(--app-info, #2080f0) 45%, transparent);
  background: color-mix(in srgb, var(--app-info, #2080f0) 8%, var(--app-card-bg, #fff));
}
.hero__chip--default {
  color: var(--app-text-secondary);
}
.hero__chip--warning {
  color: var(--app-warning, #f0a020);
  border-color: color-mix(in srgb, var(--app-warning, #f0a020) 45%, transparent);
  background: color-mix(in srgb, var(--app-warning, #f0a020) 8%, var(--app-card-bg, #fff));
}
.hero__chip--ok {
  color: var(--app-success, #18a058);
  border-color: color-mix(in srgb, var(--app-success, #18a058) 45%, transparent);
  background: color-mix(in srgb, var(--app-success, #18a058) 8%, var(--app-card-bg, #fff));
}
.hero__pulse {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  animation: hero-pulse 1.6s ease-in-out infinite;
}
@keyframes hero-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 color-mix(in srgb, currentColor 45%, transparent);
  }
  60% {
    box-shadow: 0 0 0 4px transparent;
  }
}
/* 统计行：题目数 / 报名数 / 封榜时间（团队 Hero meta 同款排版） */
.hero__meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--app-text-secondary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.hero__dot {
  opacity: 0.5;
}
.hero__meta-num {
  font-weight: 600;
  color: var(--app-text);
}
/* 动作区：报名 / 刷新；窄屏自动换行 */
.hero__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-left: auto;
}
/* 翻页时钟：报名按钮左侧（hero__actions 内 margin-left:auto 已右对齐） */
.hero__clock {
  display: flex;
  align-items: center;
  gap: 12px;
}
.hero__clock-label {
  font-size: 13px;
  font-weight: 650;
  letter-spacing: 0.02em;
  color: var(--app-text-secondary);
  text-transform: uppercase;
}
/* 翻页时钟：每组 = 数字卡 ×2，卡片中缝横线模拟翻页轴 */
.flip-clock {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.flip-clock__colon {
  font-size: 24px;
  font-weight: 750;
  color: var(--app-text-secondary);
  line-height: 1;
  transform: translateY(-2px);
}
.flip-clock__group {
  display: inline-flex;
  gap: 3px;
  perspective: 220px;
}
.flip-clock__card {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 54px;
  border-radius: 6px;
  background: var(--app-card-bg, #fff);
  border: 1px solid var(--app-border);
  box-shadow: 0 2px 5px rgb(0 0 0 / 10%);
  font-size: 28px;
  font-weight: 750;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  color: var(--app-text);
  overflow: hidden;
  /* 数字变化时卡片重挂载（key 绑定数字值），翻页动画重放 */
  animation: flip-fold 0.45s cubic-bezier(0.2, 0.7, 0.3, 1);
}
/* 翻页：新数字自上折下（rotateX 88° → 0，透视原点在卡顶） */
@keyframes flip-fold {
  0% {
    transform: rotateX(-88deg);
    opacity: 0.4;
  }
  100% {
    transform: rotateX(0deg);
    opacity: 1;
  }
}
/* 翻页轴中缝：横贯卡片的半透明分割线 */
.flip-clock__card::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  height: 1px;
  background: color-mix(in srgb, var(--app-border) 70%, transparent);
}
.hero__clock--scheduled .flip-clock__card {
  color: var(--app-info, #2080f0);
}
.hero__clock--running .flip-clock__card {
  color: var(--app-success, #18a058);
}

/* ---- 模块区：tab 线条直连内容，无卡片外框（团队页同款） ---- */
.module-area {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.module-tabs {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.module-tabs :deep(.n-tabs-nav) {
  padding: 4px 32px 0;
  flex-shrink: 0;
}
.module-tabs :deep(.n-tabs-tab) {
  font-size: 14px;
  padding: 12px 6px;
}
/* 非 animated 模式 naive 不渲染 pane-wrapper，pane 直接挂在 .n-tabs 下 */
.module-tabs :deep(.n-tabs-pane-wrapper),
.module-tabs :deep(.n-tab-pane) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.module-tabs :deep(.n-tab-pane) {
  padding: 16px 32px 20px;
}
/* pane 内滚动区：列表撑满，超出滚动 */
.pane-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
/* 榜单：flex-height 表格撑满剩余高度（表体内部滚动），分页条贴底 */
.board-table {
  flex: 1;
  min-height: 0;
}
/* 榜单分页条：钉在 pane 底部（表格 flex:1 吃掉剩余空间） */
.board-pager {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--app-border);
  flex-shrink: 0;
}
.pager__total {
  font-size: 12px;
  color: var(--app-text-secondary);
  font-variant-numeric: tabular-nums;
}

/* ---- 主页面板 ---- */
.announcement {
  flex-shrink: 0;
}
.announcement__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}
.announcement__time {
  font-size: 12px;
  font-weight: 400;
  color: var(--app-text-secondary);
}

.panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px 18px;
  border: 1px solid var(--app-border);
  border-radius: 0;
  background: var(--app-card-bg, #fff);
  overflow: auto;
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

/* 空态：全局 table-fill-empty 拉伸居中；tab 纵向有界，去掉 320px 下限 */
.detail-empty {
  min-height: 0;
}
.subs-hint {
  margin-bottom: 10px;
}
.frozen-hint {
  flex-shrink: 0;
}

/* ---- 窄屏 ---- */
@media (max-width: 900px) {
  .pane-scroll {
    overflow: visible;
  }
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
