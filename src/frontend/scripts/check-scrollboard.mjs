/**
 * 滚榜大屏（public/scrollboard.html）无头冒烟测试（jsdom）。
 *
 * 两组用例：
 *   A. 内置演示数据 `?mock=1`（不需要后端，随时可跑）
 *   B. 真实形状夹具 `--fixture=<json>`：由后端脚本
 *      `src/backend/scripts/gen_scrollboard_fixture.py` 用**后端真实的** `build_reveal_steps`
 *      生成并序列化，打桩 fetch 喂给页面。B 组才是「页面能否吃下线上端点输出」的验证——
 *      A 组的 mock 是前端照契约复刻的，契约漂了它会自洽通过。
 *
 * 页面形态：ICPC Resolver 式手动滚榜 —— 点「下一步」逐格揭晓，结算中的队伍钉住不动，
 * 结算完毕整行滑到最终名次，镜头跟随当前队伍。无封面、无自动播放、无领奖台。
 *
 * 校验内容：渲染行数 / 手动逐步推进 / 钉住不变式（结算中途名次不变）/
 *   滚榜不变式（结算后名次不再提升）/ 待揭晓集合单调递减 / 终局与 final_rows 逐格一致 /
 *   首血格数量 / Home·End 跳转 / DOM 落地。
 *
 * 用法：
 *   node scripts/check-scrollboard.mjs
 *   node scripts/check-scrollboard.mjs --fixture=/tmp/sb-acm.json --fixture=/tmp/sb-ioi.json
 *
 * 生成夹具：
 *   cd src/backend && python scripts/gen_scrollboard_fixture.py --out /tmp/sb-acm.json
 *   cd src/backend && python scripts/gen_scrollboard_fixture.py --rule IOI --out /tmp/sb-ioi.json
 *   cd src/backend && python scripts/gen_scrollboard_fixture.py --empty --out /tmp/sb-empty.json
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { JSDOM, VirtualConsole } from 'jsdom'

const here = dirname(fileURLToPath(import.meta.url))
const html = readFileSync(resolve(here, '../public/scrollboard.html'), 'utf8')

const args = process.argv.slice(2)
const fixturePaths = args
  .filter((a) => a.startsWith('--fixture='))
  .map((a) => a.slice('--fixture='.length))

const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const results = []
const ok = (cond, label, extra = '') => results.push({ ok: !!cond, label, extra })

// ---------------------------------------------------------------- 用例驱动

async function boot({ url, fixture }) {
  const errors = []
  const virtualConsole = new VirtualConsole()
  virtualConsole.on('jsdomError', (e) => errors.push(`运行时错误 — ${e.message}`))
  virtualConsole.on('error', (...a) => errors.push(`console.error — ${a.join(' ')}`))

  const dom = new JSDOM(html, {
    runScripts: 'dangerously',
    url,
    pretendToBeVisual: true,
    virtualConsole,
    beforeParse(window) {
      if (!fixture) return
      window.localStorage.setItem('pigeonoj.token', 'fixture-token')
      // 只打桩滚榜数据端点；页面其余行为保持真实
      window.fetch = async (path) => {
        if (!String(path).includes('/scoreboard-show')) {
          return { ok: false, status: 404, json: async () => ({ code: 1, message: `unexpected ${path}` }) }
        }
        return { ok: true, status: 200, json: async () => ({ code: 0, message: 'ok', data: fixture }) }
      }
    },
  })
  await wait(80) // 等 init() 的 await 落定
  return { dom, errors }
}

const key = (window, k) =>
  window.dispatchEvent(new window.KeyboardEvent('keydown', { key: k, bubbles: true }))

async function audit({ label, url, fixture }) {
  const { dom, errors } = await boot({ url, fixture })
  const { window } = dom
  const { document } = window
  const st = window.__sbDebug

  ok(!!st, `${label} · 页面完成初始化`)
  if (!st) { errors.forEach((e) => ok(false, `${label} · ${e}`)); dom.window.close(); return }

  const data = st.data
  const acm = data.rule_type === 'ACM'
  const steps = data.steps

  ok(document.getElementById('title').textContent === data.title, `${label} · 页眉标题取自数据包`)
  ok(document.getElementById('rulePill').textContent === data.rule_type, `${label} · 赛制标签 = ${data.rule_type}`)
  ok(document.querySelectorAll('#canvas .row').length === data.base_rows.length,
    `${label} · 榜单行数 = ${data.base_rows.length}`,
    `实得 ${document.querySelectorAll('#canvas .row').length}`)
  ok(document.querySelectorAll('#headRow .h.letter').length === data.problems.length,
    `${label} · 表头题目列 = ${data.problems.length}`)
  ok(st.applied === 0, `${label} · 起点为封榜快照`)
  ok(document.getElementById('stepCount').textContent === `0 / ${steps.length}`,
    `${label} · 步数计数 = 0 / ${steps.length}`,
    `实得 ${document.getElementById('stepCount').textContent}`)

  // ---- 空 steps 边界：封榜期间没有提交 ----
  if (steps.length === 0) {
    ok(document.getElementById('status').textContent.includes('没有待揭晓'), `${label} · 状态栏提示无待揭晓提交`)
    ok(document.getElementById('nextBtn').disabled, `${label} · 无步骤时下一步不可用`)
    document.getElementById('nextBtn').click()
    key(window, 'ArrowRight')
    await wait(10)
    ok(st.applied === 0, `${label} · 无步骤时点下一步不推进`)
    ok(document.querySelectorAll('#canvas .row').length === data.base_rows.length, `${label} · 无步骤时榜单照常渲染`)
  } else {
    ok(document.getElementById('status').textContent.includes(`${steps.length}`),
      `${label} · 起点状态栏含待揭晓总数`)

    const lastStepIdxOf = new Map()
    steps.forEach((s, i) => lastStepIdxOf.set(s.user_id, i))

    const history = new Map()       // uid -> 每步后的名次
    const perTeamRanks = new Map()  // uid -> 该队每一步揭晓后的名次（钉住校验用）
    const pendingSizes = [st.pending.size]
    let stalled = null
    let highlightBad = null
    for (let i = 0; i < steps.length; i++) {
      key(window, 'ArrowRight')
      await wait(1)
      if (st.applied !== i + 1) { stalled = `第 ${i + 1} 步后 applied=${st.applied}`; break }
      for (const uid of lastStepIdxOf.keys()) {
        if (!history.has(uid)) history.set(uid, [])
        history.get(uid).push(st.rankOf.get(uid))
      }
      if (!perTeamRanks.has(steps[i].user_id)) perTeamRanks.set(steps[i].user_id, [])
      perTeamRanks.get(steps[i].user_id).push(st.rankOf.get(steps[i].user_id))
      pendingSizes.push(st.pending.size)

      // 高亮：applied<len 时，恰好一个 .resolving，且属于下一个待结算队伍
      const hot = document.querySelectorAll('#canvas .row.resolving')
      if (i + 1 < steps.length) {
        const want = steps[i + 1].user_id
        if (hot.length !== 1 || hot[0].dataset.uid !== want) {
          highlightBad = `第 ${i + 1} 步后高亮 ${hot.length} 行（应为 1 行 uid=${want}）`
        }
      } else if (hot.length !== 0) {
        highlightBad = '全部揭晓后仍有高亮行'
      }
    }

    ok(!stalled, `${label} · 每一步都推进了进度`, stalled || '')
    ok(st.applied === steps.length, `${label} · 走完全部 ${steps.length} 步`)
    ok(!highlightBad, `${label} · 结算高亮始终跟随下一个待结算队伍`, highlightBad || '')

    // 钉住不变式：一队结算中途（最后一步之前）名次不变，结算完才移动
    let pinBreak = null
    for (const [uid, ranks] of perTeamRanks) {
      for (let j = 1; j < ranks.length - 1; j++) {
        if (ranks[j] !== ranks[0]) {
          pinBreak = `${st.nick.get(uid) || uid} 结算中途名次由 ${ranks[0]} 变为 ${ranks[j]}（应钉住）`
          break
        }
      }
      if (pinBreak) break
    }
    ok(!pinBreak, `${label} · 钉住不变式：结算中途行不移动`, pinBreak || '')

    // 滚榜不变式：揭晓按「最终名次从差到好」推进，队伍结算后状态冻结，后续只会有
    // 更强的队伍揭晓后挤到它上面 —— 已结算队伍名次只会被往下压，不会再提升。
    let monoBreak = null
    for (const [uid, lastIdx] of lastStepIdxOf) {
      const rs = history.get(uid) || []
      for (let i = lastIdx; i < rs.length; i++) {
        if (rs[i] === undefined) { monoBreak = `${uid} 在结算后丢失名次`; break }
        if (i > lastIdx && rs[i] < rs[i - 1]) {
          monoBreak = `${steps[lastIdx].nickname} 结算后名次由 ${rs[i - 1]} 提升到 ${rs[i]}`
          break
        }
      }
      if (monoBreak) break
    }
    ok(!monoBreak, `${label} · 滚榜不变式：结算后名次不再提升`, monoBreak || '')
    ok(pendingSizes[pendingSizes.length - 1] === 0, `${label} · 结束后无待揭晓格子`)
    ok(pendingSizes.every((v, i) => i === 0 || v <= pendingSizes[i - 1]), `${label} · 待揭晓集合单调递减`)

    // ---- 终局与 final_rows 对齐 ----
    let rowMismatch = null
    for (const fr of data.final_rows) {
      const mine = st.rows.find((r) => r.uid === fr.user_id)
      if (!mine) { rowMismatch = `缺少队伍 ${fr.nickname}`; break }
      const mineTotal = acm ? mine.totalPenalty : mine.totalScore
      const frTotal = acm ? fr.total_penalty : fr.total_score
      if (mine.rank !== fr.rank) { rowMismatch = `${fr.nickname} 名次 ${mine.rank} ≠ 权威 ${fr.rank}`; break }
      if (mine.solved !== fr.solved) { rowMismatch = `${fr.nickname} 通过数 ${mine.solved} ≠ ${fr.solved}`; break }
      if (mineTotal !== frTotal) { rowMismatch = `${fr.nickname} ${acm ? '罚时' : '总分'} ${mineTotal} ≠ ${frTotal}`; break }
    }
    ok(!rowMismatch, `${label} · 终局榜与 final_rows 一致`, rowMismatch || '')

    // 后端 steps 按赛制裁剪字段：IOI 的 penalty 恒为 0（final_rows 带真值，但 steps 不携带，
    // 页面无从还原）。IOI 的排序（-总分,-通过数）与格子展示都只用 score / attempts，
    // penalty 不参与，故该项在 IOI 下不比对。ACM 的 score 则要求严格一致（页面补成满分）。
    const comparePenalty = acm
    let cellMismatch = null
    for (const fr of data.final_rows) {
      for (const c of fr.cells) {
        const mine = st.cellState.get(fr.user_id)?.get(c.problem_id)
        if (!mine) { cellMismatch = `(${fr.nickname}, ${c.letter}) 缺格`; break }
        if (mine.accepted !== c.accepted || mine.attempts !== c.attempts
          || (comparePenalty && mine.penalty !== c.penalty) || mine.score !== c.score) {
          cellMismatch = `(${fr.nickname}, ${c.letter}) 页面 ${mine.accepted}/${mine.attempts}/${mine.penalty}/${mine.score}` +
            ` ≠ 权威 ${c.accepted}/${c.attempts}/${c.penalty}/${c.score}`
          break
        }
      }
      if (cellMismatch) break
    }
    ok(!cellMismatch, `${label} · 每个题目格与权威终局一致`, cellMismatch || '')

    // 首血格（ACM）：每题至多一格 .first，且总数 = 有 AC 的题目数
    if (acm) {
      const expectFirst = new Set()
      for (const fr of data.final_rows) {
        for (const c of fr.cells) if (c.accepted) expectFirst.add(c.problem_id)
      }
      const got = document.querySelectorAll('#canvas .cell.first').length
      ok(got === expectFirst.size, `${label} · 首血格数量 = ${expectFirst.size}`, `实得 ${got}`)
    }
  }

  // ---- 跳转 + DOM 落地（End 走 rebuildTo，无翻牌动画，可直接校验渲染） ----
  key(window, 'Home')
  await wait(10)
  ok(st.applied === 0, `${label} · Home 回到起点`)
  ok(document.getElementById('status').textContent.includes('待揭晓')
    || document.getElementById('status').textContent.includes('没有待揭晓'),
    `${label} · 回退后状态栏恢复待命文案`)

  key(window, 'End')
  await wait(10)
  ok(st.applied === steps.length, `${label} · End 跳到终点`)
  ok(document.getElementById('status').textContent.includes('全部揭晓完毕')
    || document.getElementById('status').textContent.includes('没有待揭晓'),
    `${label} · 终点状态栏提示揭晓完毕`)

  if (data.final_rows.length > 0) {
    const rank1 = st.rows.find((r) => r.rank === 1)
    const rank1El = document.querySelector(`#canvas .row[data-uid="${rank1.uid}"]`)
    ok(rank1El.querySelector('.c.rk').textContent === '1', `${label} · 榜首行名次渲染为 1`)
    ok(rank1El.querySelector('.c.solved').textContent === String(rank1.solved), `${label} · 榜首行通过数正确`)
    ok(rank1El.style.transform === 'translateY(0px)', `${label} · 榜首行位于画布顶部`)
    ok(rank1El.querySelector('.c.nm').textContent === (st.nick.get(rank1.uid) || ''), `${label} · 榜首行队名正确`)

    const acEntry = [...st.cellState.get(rank1.uid).entries()].find(([, c]) => c.accepted)
    if (acEntry) {
      const idx = data.problems.findIndex((p) => p.problem_id === acEntry[0])
      const el = rank1El.querySelectorAll('.cell')[idx]
      ok(el.classList.contains('ac'), `${label} · AC 格带 ac 样式`)
      ok(acm ? el.textContent.startsWith('+') : el.textContent.startsWith(String(acEntry[1].score)),
        `${label} · AC 格文案正确（${el.textContent}）`)
      ok(!el.classList.contains('pending'), `${label} · 已揭晓格不再带待定标记`)
    } else {
      ok(false, `${label} · 榜首至少有一道 AC 题`)
    }
  }

  errors.forEach((e) => ok(false, `${label} · ${e}`))
  dom.window.close()
}

// ---------------------------------------------------------------- 用例清单

const cases = []
for (const p of fixturePaths) {
  const fixture = JSON.parse(readFileSync(p, 'utf8'))
  const tag = `${fixture.rule_type}${fixture.steps.length === 0 ? '/空' : ''}·夹具`
  cases.push({
    label: tag,
    url: `http://localhost/scrollboard.html?contest_id=${fixture.contest_id}`,
    fixture,
  })
}
cases.push({
  label: 'ACM·演示',
  url: 'http://localhost/scrollboard.html?mock=1&teams=22&problems=8&seed=20260903',
})
cases.push({
  label: 'IOI·演示',
  url: 'http://localhost/scrollboard.html?mock=1&teams=14&problems=6&rule=IOI&seed=77',
})

console.log('滚榜大屏 · 冒烟测试')
for (const c of cases) {
  const from = results.length
  await audit(c)
  console.log(`\n  [${c.label}]`)
  for (const r of results.slice(from)) {
    console.log(`    ${r.ok ? '✓' : '✗'} ${r.label}${r.ok || !r.extra ? '' : ` — ${r.extra}`}`)
  }
}

// 注意：results 是本进程的全部记录，不能在打印时 splice 清空，否则末尾统计恒为 0
const failed = results.filter((r) => !r.ok).length
if (!fixturePaths.length) {
  console.log('\n  ⚠ 未传 --fixture，跳过了「真实后端数据形状」用例（最有价值的一组）。')
  console.log('    生成：cd src/backend && python scripts/gen_scrollboard_fixture.py --out /tmp/sb-acm.json')
}
console.log(failed === 0 ? '\n全部通过' : `\n${failed} 项失败`)
process.exit(failed === 0 ? 0 : 1)
