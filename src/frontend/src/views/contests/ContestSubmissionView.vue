<script setup lang="ts">
/**
 * 比赛提交详情（上下文路由 /contests/:cid/submissions/:sid、/teams/:teamId/contests/:cid/submissions/:sid）：
 * 经比赛统一入口端点读取（窗口校验：比赛期间所有人不可见，赛后开放），
 * 不跳出比赛上下文；面包屑回比赛详情页。
 * 轮询与渲染经 useSubmissionDetail + SubmissionResultView 复用（H4 收敛）。
 */
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { getContestSubmission } from '@/api/contests'
import { getTeamContestSubmission } from '@/api/teams'
import SubmissionResultView from '@/components/SubmissionResultView.vue'
import { useSubmissionDetail } from '@/composables/useSubmissionDetail'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

function fetchSubmission() {
  return route.params.teamId
    ? getTeamContestSubmission(
        String(route.params.teamId),
        String(route.params.cid),
        String(route.params.sid),
      )
    : getContestSubmission(String(route.params.cid), String(route.params.sid))
}

const { submission, loading, pollingStopped, statusLabel, showScoreBox, load, refreshNow } =
  useSubmissionDetail(fetchSubmission)

function back() {
  // 团队比赛上下文：回团队路由内比赛详情
  if (route.params.teamId) {
    router.push(`/teams/${String(route.params.teamId)}/contests/${String(route.params.cid)}`)
    return
  }
  router.push(`/contests/${String(route.params.cid)}`)
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
    :back-label="t('contests.submissions.backToContest')"
    @back="back"
    @refresh="refreshNow"
  />
</template>