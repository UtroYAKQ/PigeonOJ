import { computed, onActivated, onDeactivated, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useTimeoutFn } from '@vueuse/core'

import { submissionStatusLabelKey } from '@/constants/submissionStatus'
import { message } from '@/utils/feedback'
import type { Submission } from '@/types'

/** 自动刷新上限：2s × 150 = 5 分钟，避免无退避的无限轮询 */
const MAX_POLLS = 150
const POLL_INTERVAL_MS = 2000

/**
 * 评测结果页共享 composable（H4 收敛）：SubmissionView / ProblemSubmissionDetailView /
 * ContestSubmissionView 三份重复的轮询拉取、状态与计分派生合并于此。
 *
 * fetch 由各上下文提供（题目 / 题目管理 / 比赛含团队比赛各自选端点）；返回动作（back / refresh）
 * 与渲染由页面层负责——本 composable 不关心路由动线与 DOM。
 */
export function useSubmissionDetail(fetch: () => Promise<Submission>) {
  const { t } = useI18n()

  const submission = ref<Submission | null>(null)
  const loading = ref(false)
  const pollCount = ref(0)
  /** KeepAlive 缓存页可见标记：切走（deactivated）时暂停轮询，返回时恢复 */
  const pageActive = ref(true)

  // 链式延时轮询：上一次响应返回后再等 2s 才发起下一次（卸载自动取消）
  const scheduleNextPoll = useTimeoutFn(() => void load(true), POLL_INTERVAL_MS, {
    immediate: false,
  })

  const isRunning = computed(
    () => submission.value?.status === 'pending' || submission.value?.status === 'judging',
  )
  /** 达到轮询上限仍未出结果 → 停止自动刷新，提示手动刷新 */
  const pollingStopped = computed(() => isRunning.value && pollCount.value >= MAX_POLLS)
  const statusLabel = computed(() =>
    t(submissionStatusLabelKey(submission.value?.status ?? 'pending')),
  )
  /** 分数格 / 分数列显隐：ACM 二值计分（AC=满分否则 0）不展示 IOI 分数；非比赛提交无赛制快照 → 展示 */
  const showScoreBox = computed(() => submission.value?.rule_type !== 'ACM')

  async function load(silent = false) {
    if (!silent) loading.value = true
    try {
      submission.value = await fetch()
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

  /** 手动刷新：重置轮询计数并立即拉取 */
  function refreshNow() {
    pollCount.value = 0
    void load()
  }

  return {
    submission,
    loading,
    isRunning,
    pollingStopped,
    statusLabel,
    showScoreBox,
    load,
    refreshNow,
  }
}