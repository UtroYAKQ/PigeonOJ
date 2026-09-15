<script setup lang="ts">
/**
 * 提交评测详情（题目 / 题单 / 比赛 / 团队上下文写题后落地到本视图）：
 * 经本人提交端点读取。轮询与渲染经 useSubmissionDetail + SubmissionResultView 复用
 * （H4 收敛），本页仅保留返回动线（站内来路优先，其余按上下文回挂）。
 */
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { getSubmission } from '@/api/judge'
import SubmissionResultView from '@/components/SubmissionResultView.vue'
import { useSubmissionDetail } from '@/composables/useSubmissionDetail'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const { submission, loading, pollingStopped, statusLabel, showScoreBox, load, refreshNow } =
  useSubmissionDetail(() => getSubmission(String(route.params.id)))

/** 站内是否有来路（vue-router 在 history.state.back 记录上一跳） */
const canGoBack = computed(() => {
  const back = router.options.history.state.back
  return typeof back === 'string' && back.length > 0 && back !== route.fullPath
})
const backLabel = computed(() => {
  if (canGoBack.value) return t('problems.submission.back')
  return submission.value?.problem_id
    ? t('problems.submission.backToProblem')
    : t('problems.submission.back')
})

/** 返回：有来路时原路返回（验题工作台 / 提交列表等）；直接进入则回题目详情
 * （题单 / 比赛 / 团队上下文路由时回上下文内写题页，不跳出） */
function back() {
  if (canGoBack.value) {
    router.back()
    return
  }
  if (route.params.teamId && route.params.cid && route.params.problemId) {
    // 团队比赛上下文：回团队路由内写题页
    router.push(
      `/teams/${String(route.params.teamId)}/contests/${String(route.params.cid)}/problems/${String(route.params.problemId)}`,
    )
  } else if (route.params.setId && route.params.problemId) {
    router.push(
      `/problem-sets/${String(route.params.setId)}/problems/${String(route.params.problemId)}`,
    )
  } else if (route.params.cid && route.params.problemId) {
    router.push(`/contests/${String(route.params.cid)}/problems/${String(route.params.problemId)}`)
  } else if (route.params.teamId && route.params.problemId) {
    router.push(`/teams/${String(route.params.teamId)}/problems/${String(route.params.problemId)}`)
  } else if (submission.value?.problem_id) {
    router.push(`/problems/${submission.value.problem_id}`)
  } else {
    router.push('/problems/list')
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <SubmissionResultView
    :submission="submission"
    :loading="loading"
    :polling-stopped="pollingStopped"
    :status-label="statusLabel"
    :show-score-box="showScoreBox"
    :back-label="backLabel"
    @back="back"
    @refresh="refreshNow"
  />
</template>