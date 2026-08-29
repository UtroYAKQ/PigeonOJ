/**
 * 代码草稿 Store：按 problemId + language 索引，LRU 淘汰，localStorage 持久化。
 *
 * 上限 20 份草稿（Monaco 编辑器代码通常 < 200KB/题，总量可控）。
 * 提交成功不主动清草稿——用户可能反复修改后重新提交；仅靠 LRU 做容量兜底。
 * 切换语言时各自保留（python 草稿不影响 cpp 草稿）。
 */
import { defineStore } from 'pinia'

export interface CodeDraftItem {
  code: string
  language: string
  updatedAt: number
}

const STORAGE_KEY = 'pigeonoj.codeDrafts.v1'
const MAX_ITEMS = 20

type DraftMap = Record<string, CodeDraftItem>

function loadAll(): DraftMap {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as DraftMap) : {}
  } catch {
    return {}
  }
}

function persist(map: DraftMap) {
  // 按 updatedAt 降序，保留最新 MAX_ITEMS 份（LRU 淘汰）
  const entries = Object.entries(map).sort(([, a], [, b]) => b.updatedAt - a.updatedAt)
  const kept = Object.fromEntries(entries.slice(0, MAX_ITEMS))
  localStorage.setItem(STORAGE_KEY, JSON.stringify(kept))
}

export const useCodeStore = defineStore('code', {
  getters: {
    /** 按 problemId:language 取草稿（不存在返回 undefined） */
    draft:
      () =>
      (problemId: string, language: string): CodeDraftItem | undefined => {
        const map = loadAll()
        return map[`${problemId}:${language}`]
      },
  },
  actions: {
    /** 保存/更新草稿：立即写 localStorage */
    save(problemId: string, language: string, code: string) {
      const map = loadAll()
      map[`${problemId}:${language}`] = { code, language, updatedAt: Date.now() }
      persist(map)
    },
  },
})
