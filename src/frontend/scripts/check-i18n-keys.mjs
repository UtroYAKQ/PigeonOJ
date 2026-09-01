// 悬空 i18n 键扫描：页面/路由引用的 contests.* 键 vs 语言包实际定义
import fs from 'fs'
import { execSync } from 'child_process'

const locales = {}
for (const f of ['zh-CN', 'en-US']) {
  locales[f] = fs.readFileSync(`src/i18n/locales/${f}/contests.ts`, 'utf8')
}
const repoRoot = execSync('git rev-parse --show-toplevel', { encoding: 'utf8' }).trim()
// git ls-files 只列已跟踪文件（新建文件漏检）→ 用目录遍历兜底
const walk = (dir) =>
  fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = `${dir}/${e.name}`
    return e.isDirectory() ? walk(full) : full.endsWith('.vue') || full.endsWith('.ts') ? [full] : []
  })
const files = [
  ...execSync('git ls-files src/frontend/src', { encoding: 'utf8', cwd: repoRoot })
    .split('\n')
    .filter((p) => p.endsWith('.vue') || p.endsWith('.ts'))
    .map((p) => p.replace(/^src\/frontend\//, '')),
  ...walk('src/views'),
  ...walk('src/router'),
  ...walk('src/components'),
].filter((v, i, a) => a.indexOf(v) === i)

const used = new Set()
const tRe = /t\(['"](contests\.[a-zA-Z0-9_.]+)['"]/g
const metaRe = /titleKey: '(contests\.[a-zA-Z0-9_.]+)'/g
for (const file of files) {
  if (file.includes('i18n/locales')) continue
  const s = fs.readFileSync(file, 'utf8')
  for (const m of s.matchAll(tRe)) used.add(m[1])
  for (const m of s.matchAll(metaRe)) used.add(m[1])
}

let bad = 0
for (const key of used) {
  const props = key.split('.').slice(1)
  for (const f of ['zh-CN', 'en-US']) {
    let src = locales[f]
    let cursor = src.indexOf('contests:')
    let ok = true
    for (const p of props) {
      const re = new RegExp(`\\b${p}\\s*:`)
      const seg = src.slice(cursor)
      const m = seg.match(re)
      if (!m) { ok = false; break }
      cursor += m.index + m[0].length
    }
    if (!ok) { console.log(`悬空键 [${f}]:`, key); bad++ }
  }
}
console.log(bad ? `${bad} 处悬空引用` : `contests.* ${used.size} 个被引用键全部存在`)
