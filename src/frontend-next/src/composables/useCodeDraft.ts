import { nextTick, watch, type Ref } from 'vue'
import { useDebounceFn } from '@vueuse/core'

import { useUserStore } from '@/stores/user'
import type { ProblemLanguage } from '@/types'

/**
 * 题目代码本地草稿：按「用户 + 题目 + 语言」持久化到 localStorage。
 *
 * 解决「提交后返回 / 切换页面代码丢失」：进入页面 restore() 恢复，
 * 编辑防抖写入；切换语言先存旧语言草稿再载入新语言草稿（无则清空）。
 * LRU 清理避免无限占用（后端 user_code_drafts 已于迁移 0008 移除，故走本地）。
 */

const INDEX_KEY = 'pigeonoj.codeDrafts.index'
const MAX_ENTRIES = 40

function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}
function safeSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // 配额 / 隐私模式：静默降级为不持久化
  }
}
function safeRemove(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch {
    // 忽略
  }
}

interface IndexEntry {
  key: string
  updatedAt: number
}

function readIndex(): IndexEntry[] {
  const raw = safeGet(INDEX_KEY)
  if (!raw) return []
  try {
    const arr = JSON.parse(raw)
    return Array.isArray(arr) ? arr : []
  } catch {
    return []
  }
}

/** 记录最近写入并做 LRU 清理，超出上限的旧草稿直接删除 */
function touchIndex(key: string): void {
  const index = readIndex().filter((e) => e.key !== key)
  index.unshift({ key, updatedAt: Date.now() })
  const evicted = index.splice(MAX_ENTRIES)
  for (const e of evicted) safeRemove(e.key)
  safeSet(INDEX_KEY, JSON.stringify(index))
}

export function useCodeDraft(opts: {
  problemId: () => string
  code: Ref<string>
  language: Ref<ProblemLanguage>
}) {
  const userStore = useUserStore()
  // restore / 语言切换期间的程序性赋值不触发保存，避免互相覆盖
  let restoring = false

  const uid = () => userStore.user?.id ?? 'guest'
  const codeKey = (lang: string) => `pigeonoj.codeDraft.${uid()}.${opts.problemId()}.${lang}`
  const metaKey = () => `pigeonoj.codeDraftMeta.${uid()}.${opts.problemId()}`

  function saveDraft(lang: string) {
    safeSet(codeKey(lang), opts.code.value)
    safeSet(metaKey(), JSON.stringify({ language: lang, updatedAt: Date.now() }))
    touchIndex(codeKey(lang))
  }

  const debouncedSave = useDebounceFn(() => saveDraft(opts.language.value), 400)

  /** 进入页面时恢复：优先用 meta 记住的语言，再载入该语言草稿 */
  function restore() {
    restoring = true
    let lang: ProblemLanguage = opts.language.value
    const metaRaw = safeGet(metaKey())
    if (metaRaw) {
      try {
        const meta = JSON.parse(metaRaw)
        if (meta?.language) lang = meta.language
      } catch {
        // 忽略损坏的 meta
      }
    }
    opts.language.value = lang
    opts.code.value = safeGet(codeKey(lang)) ?? ''
    nextTick(() => {
      restoring = false
    })
  }

  watch(opts.code, () => {
    if (!restoring) debouncedSave()
  })

  watch(opts.language, (newLang, oldLang) => {
    if (restoring || newLang === oldLang) return
    // 先存旧语言草稿，再载入新语言草稿（无则清空），并更新 meta 语言
    saveDraft(oldLang)
    restoring = true
    opts.code.value = safeGet(codeKey(newLang)) ?? ''
    saveDraft(newLang)
    nextTick(() => {
      restoring = false
    })
  })

  return { restore }
}
