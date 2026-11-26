import { computed, ref } from 'vue'
import { onActivated, onDeactivated } from 'vue'
import { useTimeoutFn } from '@vueuse/core'
import { useI18n } from 'vue-i18n'

import { message } from '@/utils/feedback'
import type { Submission } from '@/types'

const MAX_POLLS = 150
const POLL_INTERVAL_MS = 2000

/**
 * 提交结果轮询：pending/judging 时链式延时刷新（上一次响应后再等 2s），
 * KeepAlive 缓存页切走暂停、返回恢复；达到上限停止并提示手动刷新。
 * 调用方负责首次 load() 与路由/返回按钮。
 */
export function useSubmissionPolling(fetcher: () => Promise<Submission>) {
  const { t } = useI18n()
  const submission = ref<Submission | null>(null)
  const loading = ref(false)
  const pollCount = ref(0)
  const pageActive = ref(true)

  const scheduleNextPoll = useTimeoutFn(() => void load(true), POLL_INTERVAL_MS, {
    immediate: false,
  })

  const isRunning = computed(
    () => submission.value?.status === 'pending' || submission.value?.status === 'judging',
  )
  const pollingStopped = computed(() => isRunning.value && pollCount.value >= MAX_POLLS)

  async function load(silent = false): Promise<void> {
    if (!silent) loading.value = true
    try {
      submission.value = await fetcher()
      if (isRunning.value && !pollingStopped.value && pageActive.value) {
        pollCount.value += 1
        scheduleNextPoll.start()
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : t('problems.submission.loadFailed'))
    } finally {
      if (!silent) loading.value = false
    }
  }

  onDeactivated(() => {
    pageActive.value = false
    scheduleNextPoll.stop()
  })
  onActivated(() => {
    pageActive.value = true
    if (isRunning.value && !pollingStopped.value) scheduleNextPoll.start()
  })

  function refreshNow(): void {
    pollCount.value = 0
    void load()
  }

  return { submission, loading, pollingStopped, load, refreshNow }
}
