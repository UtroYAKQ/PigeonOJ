import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

import zh from './locales/zh-CN'
import en from './locales/en-US'

function walk(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      return entry.name === 'node_modules' || entry.name === 'i18n' ? [] : walk(full)
    }
    return full.endsWith('.vue') || full.endsWith('.ts') ? [full] : []
  })
}

function lookup(messages: Record<string, unknown>, key: string): unknown {
  return key
    .split('.')
    .reduce<unknown>(
      (cursor, part) =>
        cursor && typeof cursor === 'object'
          ? (cursor as Record<string, unknown>)[part]
          : undefined,
      messages,
    )
}

describe('i18n 静态键完整性', () => {
  it("模板 / 路由中 t('literal') 与 titleKey 均在中英文语言包中存在", () => {
    const files = walk(path.resolve('src')).filter(
      (file) =>
        !file.endsWith('.spec.ts') &&
        !file.includes(`${path.sep}i18n${path.sep}`) &&
        !file.includes(`${path.sep}types${path.sep}components.d.ts`),
    )

    const keys = new Set<string>()
    const tPattern = /\bt\(\s*['"]([a-zA-Z0-9_.]+)['"]/g
    const titlePattern = /titleKey:\s*['"]([a-zA-Z0-9_.]+)['"]/g
    for (const file of files) {
      const source = fs.readFileSync(file, 'utf8')
      for (const match of source.matchAll(tPattern)) keys.add(match[1]!)
      for (const match of source.matchAll(titlePattern)) keys.add(match[1]!)
    }

    const dynamicKeys = [
      ...[
        'pending',
        'judging',
        'accepted',
        'ok',
        'wrong_answer',
        'time_limit_exceeded',
        'memory_limit_exceeded',
        'output_limit_exceeded',
        'runtime_error',
        'compile_error',
        'system_error',
      ].map((status) => `problems.status.${status}`),
      ...['private', 'public', 'admin_visible', 'team_visible', 'org_visible'].map(
        (visibility) => `problems.visibility.${visibility}`,
      ),
      ...['published', 'draft', 'draft_spj', 'duplicate', 'skipped_spj', 'failed'].map(
        (status) => `problems.importFps.status_${status}`,
      ),
      ...Array.from({ length: 10 }, (_, index) => `home.tips.t${index + 1}`),
      ...['site', 'auth_email', 'team', 'contest', 'sandbox', 'log', 'community'].map(
        (category) => `dictionary.category.${category}`,
      ),
      ...['problem', 'solution', 'code_share', 'post', 'comment', 'user'].map(
        (type) => `dictionary.reportType.${type}`,
      ),
      ...['pending', 'handled', 'ignored'].map((status) => `dictionary.reportStatus.${status}`),
      ...['error', 'warning', 'fatal'].map((level) => `dictionary.logLevel.${level}`),
      ...['online', 'offline'].map((status) => `dictionary.sandboxStatus.${status}`),
      ...['admin', 'user'].map((role) => `user.role.${role}`),
      ...['active', 'frozen', 'banned', 'deleted'].map((status) => `user.status.${status}`),
    ]
    for (const key of dynamicKeys) keys.add(key)

    const missing: string[] = []
    for (const key of [...keys].sort()) {
      if (lookup(zh as Record<string, unknown>, key) === undefined) missing.push(`zh-CN:${key}`)
      if (lookup(en as Record<string, unknown>, key) === undefined) missing.push(`en-US:${key}`)
    }

    expect(missing).toEqual([])
  })
})
