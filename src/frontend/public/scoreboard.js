import * as Core from './scoreboard-core.js'

const dictionaries = {
  'zh-CN': {
    live: '比赛实时榜 · 循环展示',
    local: '赛后滚榜 · 本机预览',
    control: '赛后滚榜 · 同步控制台',
    watch: '赛后滚榜 · 观众大屏',
    play: '播放',
    pause: '暂停',
    next: '下一步 →',
    previous: '← 上一步',
    restart: '重新播放',
    watchLink: '打开观众大屏',
    scroll: '自动滚动',
    stopScroll: '暂停滚动',
    empty: '暂无参赛选手',
    frozen: '封榜中 · 等待正式发布',
    open: '公开榜单',
    done: '揭晓完毕',
    login: '请先在本站登录后再打开大屏',
    legend: '绿色 = AC　金边 = 首次通过　? = 待揭晓',
    missing: '缺少 contest_id',
    readonly: '当前账号不能控制滚榜',
    full: '全屏',
    theme: '切换明暗',
    retry: '网络异常，正在自动重连',
    waiting: '管理员尚未创建会话，正在等待',
    confirm: '重新播放当前快照？已公开的信息不会重新保密。',
    contestant: '选手 / 队伍',
    penalty: '罚时 / 分钟',
    score: '总分',
  },
  'en-US': {
    live: 'Live standings · rotating display',
    local: 'Resolver · local preview',
    control: 'Resolver · shared controls',
    watch: 'Resolver · audience display',
    play: 'Play',
    pause: 'Pause',
    next: 'Next →',
    previous: '← Previous',
    restart: 'Restart',
    watchLink: 'Open audience display',
    scroll: 'Auto-scroll',
    stopScroll: 'Pause scrolling',
    empty: 'No participants yet',
    frozen: 'Frozen · awaiting publication',
    open: 'Published standings',
    done: 'All results revealed',
    login: 'Sign in to this site before opening the scoreboard',
    legend: 'Green = AC　Gold = first solve　? = unrevealed',
    missing: 'Missing contest_id',
    readonly: 'This account cannot control the resolver',
    full: 'Fullscreen',
    theme: 'Toggle theme',
    retry: 'Connection lost; reconnecting automatically',
    waiting: 'Waiting for the organizer to prepare a session',
    confirm: 'Replay this snapshot? Previously revealed information remains public.',
    contestant: 'Contestant / team',
    penalty: 'Penalty / min',
    score: 'Score',
  },
}
const params = new URLSearchParams(location.search)
const contestId = params.get('contest_id'),
  teamId = params.get('team_id')
const mode = ['live', 'local', 'control', 'watch'].includes(params.get('mode'))
  ? params.get('mode')
  : 'local'
const $ = (id) => document.getElementById(id)
const state = {
  data: null,
  rows: [],
  cursor: 0,
  playing: false,
  speed: 1,
  busy: false,
  poll: null,
  timer: null,
  scroll: mode === 'live',
  scrollSpeed: 1,
  frame: null,
  lastFrame: 0,
  bottomSince: 0,
  disposed: false,
  abort: null,
  lang: params.get('lang') === 'en-US' ? 'en-US' : 'zh-CN',
}
const t = (key) => dictionaries[state.lang][key]
const contestPath = teamId
  ? `/teams/${encodeURIComponent(teamId)}/contests/${encodeURIComponent(contestId)}`
  : `/contests/${encodeURIComponent(contestId)}`
const sessionPath = `/contests/${encodeURIComponent(contestId)}/scoreboard-session`
const prepareBtn = document.createElement('button')
prepareBtn.id = 'prepareBtn'
prepareBtn.type = 'button'
$('revealControls').append(prepareBtn)
dictionaries['zh-CN'].prepare = '重新准备数据'
dictionaries['en-US'].prepare = 'Prepare new snapshot'
dictionaries['zh-CN'].prepareConfirm =
  '重新读取已结算的比赛数据并创建新快照？全部观众页面的进度将重置。'
dictionaries['en-US'].prepareConfirm =
  'Create a new snapshot from settled results? This resets progress for all audience displays.'

async function api(path, method = 'GET', body) {
  const token = localStorage.getItem('pigeonoj.token')
  if (!token) throw new Error(t('login'))
  const response = await fetch(`/api/v1${path}`, {
    method,
    cache: 'no-store',
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
    signal: state.abort?.signal,
  })
  const result = await response.json()
  if (!response.ok || result.code !== 0) {
    const error = new Error(result.message || `HTTP ${response.status}`)
    error.status = response.status
    throw error
  }
  return result.data
}

function errorMessage(message = '') {
  $('error').hidden = !message
  $('error').textContent = message
}

function labels() {
  document.documentElement.lang = state.lang
  $('modeLabel').textContent = t(mode)
  $('legend').textContent = t('legend')
  $('playBtn').textContent = t(state.playing ? 'pause' : 'play')
  for (const [id, key] of [
    ['prevBtn', 'previous'],
    ['nextBtn', 'next'],
    ['restartBtn', 'restart'],
    ['watchBtn', 'watchLink'],
  ])
    $(id).textContent = t(key)
  $('scrollBtn').textContent = t(state.scroll ? 'stopScroll' : 'scroll')
  for (const [id, key] of [
    ['fullscreenBtn', 'full'],
    ['themeBtn', 'theme'],
  ]) {
    $(id).title = t(key)
    $(id).setAttribute('aria-label', t(key))
  }
  $('language').value = state.lang
  if (state.data) $('status').textContent = state.data.board_frozen ? t('frozen') : t('open')
  prepareBtn.textContent = t('prepare')
  prepareBtn.hidden = mode !== 'control'
  prepareBtn.disabled = state.busy
}

function render(rows, currentStep = null) {
  const wrap = $('boardWrap'),
    data = state.data,
    escape = Core.escapeHtml
  const before = new Map(
    [...wrap.querySelectorAll('tbody tr')].map((el) => [
      el.dataset.uid,
      el.getBoundingClientRect().top,
    ]),
  )
  const oldScroll = wrap.scrollTop,
    first = new Map()
  for (const row of rows)
    for (const cell of row.cells) {
      if (!cell.accepted || !cell.accepted_at) continue
      const at = Date.parse(cell.accepted_at)
      if (!first.has(cell.problem_id) || at < first.get(cell.problem_id))
        first.set(cell.problem_id, at)
    }
  const headers = data.problems
    .map(
      (p) =>
        `<th class="problem">${escape(p.letter)}${data.rule_type === 'IOI' ? `<small> / ${p.score}</small>` : ''}</th>`,
    )
    .join('')
  const body = rows
    .map((row) => {
      const cells = new Map(row.cells.map((c) => [c.problem_id, c]))
      return `<tr data-uid="${escape(row.user_id)}"${currentStep?.user_id === row.user_id ? ' class="focus"' : ''}><td class="rank">${row.rank}</td><td class="name" title="${escape(row.nickname)}">${escape(row.nickname)}</td><td class="solved">${row.solved}</td><td class="total">${data.rule_type === 'ACM' ? row.total_penalty : row.total_score}</td>${data.problems
        .map((p) => {
          const c = cells.get(p.problem_id)
          return `<td data-pid="${escape(p.problem_id)}">${Core.cellMarkup(c, data.rule_type, c?.accepted && Date.parse(c.accepted_at) === first.get(p.problem_id))}</td>`
        })
        .join('')}</tr>`
    })
    .join('')
  wrap.innerHTML = `<table style="min-width:${Math.max(700, 474 + data.problems.length * 90)}px"><thead><tr><th class="rank">#</th><th class="name">${t('contestant')}</th><th class="solved">AC</th><th class="total">${t(data.rule_type === 'ACM' ? 'penalty' : 'score')}</th>${headers}</tr></thead><tbody>${body}</tbody></table>${rows.length ? '' : `<div class="empty">${t('empty')}</div>`}`
  wrap.scrollTop = oldScroll
  state.rows = rows
  for (const el of wrap.querySelectorAll('tbody tr')) {
    const oldTop = before.get(el.dataset.uid)
    if (oldTop === undefined || !currentStep) continue
    const delta = oldTop - el.getBoundingClientRect().top
    if (delta) {
      el.style.transition = 'none'
      el.style.transform = `translateY(${delta}px)`
      requestAnimationFrame(() => {
        el.style.transition = ''
        el.style.transform = ''
      })
    }
    if (el.dataset.uid === currentStep.user_id) {
      el.querySelector(`[data-pid="${CSS.escape(currentStep.problem_id)}"] .cell`)?.classList.add(
        'flash',
      )
      el.scrollIntoView?.({
        block: 'center',
        behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',
      })
    }
  }
}

function updateControls() {
  const total = state.data?.total_steps ?? state.data?.steps?.length ?? 0
  $('revealControls').hidden =
    mode === 'live' || mode === 'watch' || (mode === 'control' && !state.data?.can_control)
  $('watchBtn').hidden = mode !== 'control'
  $('prevBtn').disabled = state.busy || state.cursor === 0
  $('nextBtn').disabled = state.busy || state.cursor >= total
  $('playBtn').disabled = state.busy || total === 0 || (!state.playing && state.cursor >= total)
  $('restartBtn').disabled = state.busy || !state.cursor
  $('speedBtn').disabled = state.busy
  $('speedBtn').textContent = `×${state.speed}`
  $('progress').textContent =
    mode === 'live'
      ? `${state.rows.length}`
      : `${state.cursor} / ${total}${state.cursor === total ? ` · ${t('done')}` : ''}`
  labels()
}

function localProject(animate = true) {
  render(
    Core.replayRows(state.data, state.cursor),
    animate && state.cursor ? state.data.steps[state.cursor - 1] : null,
  )
  updateControls()
}

function stopLocalTimer() {
  if (state.timer !== null) clearTimeout(state.timer)
  state.timer = null
}
function scheduleLocal() {
  stopLocalTimer()
  if (!state.playing || state.disposed || document.hidden) return
  state.timer = setTimeout(() => {
    state.cursor = Math.min(state.data.steps.length, state.cursor + 1)
    if (state.cursor >= state.data.steps.length) state.playing = false
    localProject()
    scheduleLocal()
  }, 1800 / state.speed)
}

async function command(action) {
  if (state.busy || !state.data || mode === 'watch' || mode === 'live') return
  if (action === 'restart' && !window.confirm(t('confirm'))) return
  if (action === 'prepare' && !window.confirm(t('prepareConfirm'))) return
  const speed = state.speed === 4 ? 1 : state.speed * 2
  if (mode === 'local') {
    if (action === 'play') state.playing = !state.playing
    else if (action === 'speed') state.speed = speed
    else {
      state.playing = false
      state.cursor =
        action === 'next'
          ? Math.min(state.data.steps.length, state.cursor + 1)
          : action === 'previous'
            ? Math.max(0, state.cursor - 1)
            : 0
    }
    localProject(action === 'next')
    scheduleLocal()
    return
  }
  if (!state.data.can_control) {
    errorMessage(t('readonly'))
    return
  }
  state.busy = true
  updateControls()
  try {
    acceptSession(
      await api(`${sessionPath}/commands`, 'POST', {
        action: action === 'play' && state.playing ? 'pause' : action,
        speed,
        revision: state.data.revision,
        command_id: crypto.randomUUID(),
      }),
    )
    errorMessage()
  } catch (error) {
    errorMessage(error.message)
    if (error.status === 409) {
      state.busy = false
      await refresh()
    }
  } finally {
    state.busy = false
    updateControls()
  }
}

function acceptSession(data) {
  if (state.disposed) return
  if (
    state.data &&
    state.data.id === data.id &&
    (data.revision < state.data.revision ||
      (data.revision === state.data.revision && data.cursor < state.cursor))
  )
    return
  const changed =
    !state.data ||
    data.id !== state.data.id ||
    data.revision !== state.data.revision ||
    data.cursor !== state.cursor
  state.data = data
  state.cursor = data.cursor
  state.playing = data.playing
  state.speed = data.speed
  $('title').textContent = data.title
  $('status').textContent = data.board_frozen ? t('frozen') : t('open')
  $('updated').textContent = new Date(data.server_time).toLocaleTimeString(state.lang)
  if (changed) render(data.rows, data.current_step)
  updateControls()
}

async function refresh() {
  if (state.disposed || document.hidden || state.busy) return
  try {
    if (mode === 'live') {
      const [detail, board] = await Promise.all([api(contestPath), api(`${contestPath}/board`)])
      if (state.disposed) return
      state.data = {
        ...board,
        problems: board.problems || detail.problems || [],
        title: detail.title,
      }
      $('title').textContent = detail.title
      $('status').textContent = board.board_frozen ? t('frozen') : t('open')
      $('updated').textContent = new Date(board.generated_at || Date.now()).toLocaleTimeString(
        state.lang,
      )
      render(board.rows)
      updateControls()
    } else if (mode === 'watch' || mode === 'control') acceptSession(await api(sessionPath))
    errorMessage()
  } catch (error) {
    if (error.name !== 'AbortError')
      errorMessage(
        error.status === 404 && mode === 'watch'
          ? t('waiting')
          : `${error.message} · ${t('retry')}`,
      )
  }
}

function schedulePoll() {
  clearTimeout(state.poll)
  if (mode === 'local' || state.disposed || document.hidden) return
  state.poll = setTimeout(
    async () => {
      await refresh()
      schedulePoll()
    },
    mode === 'live' ? 15000 : state.playing ? Math.min(750, 900 / state.speed) : 750,
  )
}

function scrollFrame(time) {
  if (state.disposed) return
  const elapsed = state.lastFrame ? Math.min(80, time - state.lastFrame) : 0
  state.lastFrame = time
  const wrap = $('boardWrap')
  if (state.scroll && !document.hidden && wrap.scrollHeight > wrap.clientHeight + 5) {
    if (wrap.scrollTop >= wrap.scrollHeight - wrap.clientHeight - 2) {
      if (!state.bottomSince) state.bottomSince = time
      if (time - state.bottomSince > 2200) {
        wrap.scrollTop = 0
        state.bottomSince = 0
      }
    } else {
      wrap.scrollTop += elapsed * 0.025 * state.scrollSpeed
      state.bottomSince = 0
    }
  }
  state.frame = requestAnimationFrame(scrollFrame)
}

function dispose() {
  state.disposed = true
  state.abort?.abort()
  clearTimeout(state.poll)
  stopLocalTimer()
  cancelAnimationFrame(state.frame)
}
$('playBtn').onclick = () => command('play')
prepareBtn.onclick = () => command('prepare')
$('nextBtn').onclick = () => command('next')
$('prevBtn').onclick = () => command('previous')
$('restartBtn').onclick = () => command('restart')
$('speedBtn').onclick = () => command('speed')
$('scrollBtn').onclick = () => {
  state.scroll = !state.scroll
  labels()
}
$('scrollSpeedBtn').onclick = () => {
  state.scrollSpeed = state.scrollSpeed === 4 ? 1 : state.scrollSpeed * 2
  $('scrollSpeedBtn').textContent = `↕ ×${state.scrollSpeed}`
}
$('watchBtn').onclick = () => {
  const query = new URLSearchParams(params)
  query.set('mode', 'watch')
  window.open(`/scrollboard.html?${query}`, '_blank', 'noopener')
}
$('fullscreenBtn').onclick = async () => {
  try {
    if (document.fullscreenElement) await document.exitFullscreen()
    else await document.documentElement.requestFullscreen()
  } catch (error) {
    errorMessage(error.message)
  }
}
$('themeBtn').onclick = () => document.documentElement.classList.toggle('light')
$('language').onchange = () => {
  state.lang = $('language').value
  labels()
  if (state.data) {
    render(state.rows)
    updateControls()
  }
}
document.addEventListener('keydown', (event) => {
  if (['SELECT', 'INPUT', 'TEXTAREA', 'BUTTON'].includes(event.target.tagName)) return
  const action = { ' ': 'play', ArrowRight: 'next', ArrowLeft: 'previous' }[event.key]
  if (action) {
    event.preventDefault()
    void command(action)
  }
})
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    clearTimeout(state.poll)
    stopLocalTimer()
    state.lastFrame = 0
  } else {
    void refresh().finally(schedulePoll)
    scheduleLocal()
  }
})
window.addEventListener('pagehide', dispose)
window.addEventListener('pageshow', (event) => {
  if (event.persisted) location.reload()
})
async function init() {
  labels()
  if (!contestId) {
    errorMessage(t('missing'))
    return
  }
  state.abort = new AbortController()
  try {
    if (mode === 'local') {
      state.data = await api(`${contestPath}/scoreboard-show`)
      $('title').textContent = state.data.title
      $('status').textContent = state.data.board_frozen ? t('frozen') : t('open')
      localProject(false)
    } else if (mode === 'control') acceptSession(await api(sessionPath, 'POST'))
    else await refresh()
    state.frame = requestAnimationFrame(scrollFrame)
  } catch (error) {
    if (error.name !== 'AbortError') errorMessage(error.message)
  }
  schedulePoll()
}
void init()
