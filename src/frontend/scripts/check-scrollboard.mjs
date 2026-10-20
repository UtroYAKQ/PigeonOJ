/** Real DOM smoke tests driven by the backend's serialized resolver snapshots. */
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFileSync } from 'node:child_process'
import { JSDOM } from 'jsdom'
import * as Core from '../public/scoreboard-core.js'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const html = readFileSync(resolve(root, 'src/frontend/public/scrollboard.html'), 'utf8')
const script = readFileSync(resolve(root, 'src/frontend/public/scoreboard.js'), 'utf8').replace(
  "import * as Core from './scoreboard-core.js'",
  'const Core = window.__testCore',
)
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const fixturePaths = process.argv
  .slice(2)
  .filter((arg) => arg.startsWith('--fixture='))
  .map((arg) => arg.slice(10))
const python = resolve(
  root,
  process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python',
)
function generate(args) {
  if (!existsSync(python))
    throw new Error('Prepare the repository .venv or pass --fixture=<backend JSON>')
  return JSON.parse(
    execFileSync(python, ['scripts/gen_scrollboard_fixture.py', ...args], {
      cwd: resolve(root, 'src/backend'),
      encoding: 'utf8',
      maxBuffer: 32 * 1024 * 1024,
    }),
  )
}
const fixtures = fixturePaths.length
  ? fixturePaths.map((path) => JSON.parse(readFileSync(path, 'utf8')))
  : [
      generate(['--rule', 'ACM']),
      generate(['--rule', 'IOI']),
      generate(['--empty']),
      generate(['--teams', '0']),
    ]
const windows = []
function page(mode, fixture, request) {
  const dom = new JSDOM(html, {
    url: `http://localhost/scrollboard.html?contest_id=${fixture.contest_id}&mode=${mode}`,
    runScripts: 'outside-only',
    pretendToBeVisual: true,
  })
  const win = dom.window
  win.__testCore = Core
  win.structuredClone = structuredClone
  win.CSS = { escape: (s) => s }
  win.matchMedia = () => ({ matches: true })
  win.confirm = () => true
  win.localStorage.setItem('pigeonoj.token', 'test-session')
  win.fetch = async (path, options = {}) => ({
    ok: true,
    status: 200,
    json: async () => ({ code: 0, data: await request(path, options) }),
  })
  win.eval(script)
  windows.push(win)
  return win
}
function close(win) {
  win.dispatchEvent(new win.Event('pagehide'))
  win.close()
}
function assertDom(win, expected) {
  const rows = [...win.document.querySelectorAll('tbody tr')]
  assert.deepEqual(
    rows.map((el) => el.dataset.uid),
    expected.map((row) => row.user_id),
  )
  for (let i = 0; i < rows.length; i++) {
    assert.equal(Number(rows[i].querySelector('.solved').textContent), expected[i].solved)
    for (const cell of expected[i].cells) {
      const rendered = rows[i].querySelector(`[data-pid="${cell.problem_id}"] .cell`)
      assert.ok(rendered, 'problem objects must be mapped by problem_id, not used as map keys')
      assert.equal(rendered.classList.contains('pending'), cell.pending > 0)
      if (cell.accepted) assert.ok(rendered.classList.contains('ac'))
    }
  }
}

try {
  for (const fixture of fixtures) {
    const total = fixture.steps.length
    assert.deepEqual(Core.replayRows(fixture, 0), fixture.base_rows)
    assert.deepEqual(
      Core.replayRows(fixture, total),
      fixture.final_rows,
      'backend snapshot and frontend final state must match cell-for-cell',
    )
    const win = page('local', fixture, () => fixture)
    await wait(15)
    assertDom(win, fixture.base_rows)
    for (let i = 0; i < total; i++) win.document.getElementById('nextBtn').click()
    assertDom(win, fixture.final_rows)
    if (total) {
      win.document.getElementById('prevBtn').click()
      assertDom(win, Core.replayRows(fixture, total - 1))
      win.document.getElementById('restartBtn').click()
      assertDom(win, fixture.base_rows)
      win.document.getElementById('speedBtn').click()
      win.document.getElementById('speedBtn').click()
      win.document.getElementById('playBtn').click()
      await wait(500)
      assert.match(win.document.getElementById('progress').textContent, /^1 \/ /)
      win.document.getElementById('playBtn').click()
      const progress = win.document.getElementById('progress').textContent
      await wait(500)
      assert.equal(
        win.document.getElementById('progress').textContent,
        progress,
        'pause must stop automatic advancement',
      )
    }
    assert.equal(win.document.getElementById('error').hidden, true)
    close(win)
    console.log(
      `PASS ${fixture.rule_type}: ${fixture.base_rows.length} rows, ${total} steps; exact final, DOM, rewind and playback`,
    )
  }

  const fixture = fixtures.find((f) => f.steps.length > 1)
  if (fixture) {
    let cursor = 0,
      revision = 0
    const calls = []
    function projection() {
      return {
        id: fixture.contest_id,
        contest_id: fixture.contest_id,
        title: fixture.title,
        rule_type: fixture.rule_type,
        board_frozen: true,
        problems: fixture.problems,
        rows: Core.replayRows(fixture, cursor),
        cursor,
        revision,
        total_steps: fixture.steps.length,
        playing: false,
        speed: 1,
        server_time: new Date().toISOString(),
        can_control: true,
        current_step: cursor ? fixture.steps[cursor - 1] : null,
      }
    }
    const request = (path, options) => {
      calls.push(path)
      assert.ok(
        !path.endsWith('/scoreboard-show'),
        'shared displays must never download future steps',
      )
      if (path.endsWith('/commands')) {
        const body = JSON.parse(options.body)
        assert.equal(body.revision, revision)
        cursor++
        revision++
      }
      return projection()
    }
    const control = page('control', fixture, request),
      audience1 = page('watch', fixture, request),
      audience2 = page('watch', fixture, request)
    await wait(20)
    assert.equal(audience1.document.getElementById('revealControls').hidden, true)
    control.document.getElementById('nextBtn').click()
    await wait(850)
    for (const audience of [audience1, audience2]) {
      assert.match(audience.document.getElementById('progress').textContent, /^1 \/ /)
      assertDom(audience, Core.replayRows(fixture, 1))
    }
    close(audience1)
    const reconnected = page('watch', fixture, request)
    await wait(20)
    assertDom(reconnected, Core.replayRows(fixture, 1))
    close(control)
    close(audience2)
    close(reconnected)
    console.log('PASS shared controller + two audience pages + reconnect; projection-only requests')
  }
  const liveFixture = fixtures[0]
  const live = page('live', liveFixture, (path) =>
    path.endsWith('/board')
      ? { ...liveFixture, rows: liveFixture.base_rows, generated_at: new Date().toISOString() }
      : liveFixture,
  )
  await wait(20)
  assertDom(live, liveFixture.base_rows)
  assert.equal(live.document.getElementById('revealControls').hidden, true)
  const button = live.document.getElementById('scrollBtn')
  assert.match(button.textContent, /暂停/)
  button.click()
  assert.match(button.textContent, /自动/)
  close(live)
  console.log('PASS live standings and independent scrolling control')
} finally {
  windows.forEach(close)
}
