<script setup lang="ts">
/**
 * 比赛提交详情（上下文路由 /contests/:cid/submissions/:sid，团队路由同构）：
 * 经比赛统一入口端点读取（比赛期间所有人不可见，赛后开放），不跳出比赛上下文。
 */
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { getContestSubmission } from '@/api/contests'
import { getTeamContestSubmission } from '@/api/teams'
import SubmissionResultPage from '@/components/submission/SubmissionResultPage.vue'
import { useSubmissionPolling } from '@/composables/useSubmissionPolling'
import type { Submission } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const contestId = computed(() => String(route.params.cid))
const teamId = computed(() => (route.params.teamId ? String(route.params.teamId) : null))

const { submission, loading, pollingStopped, load, refreshNow } = useSubmissionPolling(() =>
  teamId.value
    ? getTeamContestSubmission(teamId.value, contestId.value, String(route.params.sid))
    : getContestSubmission(contestId.value, String(route.params.sid)),
)

/** ACM 二值分（AC=满分否则 0）不展示为 IOI 分数框：置空分数让共享结果组件隐藏该瓦片 */
const displaySubmission = computed<Submission | null>(() => {
  const current = submission.value
  if (!current) return null
  if (current.rule_type === 'ACM' && current.score !== null) {
    return { ...current, score: null }
  }
  return current
})

const backLabel = computed(() => t('contests.submissions.backToContest'))

function back(): void {
  void router.push(
    teamId.value
      ? `/teams/${teamId.value}/contests/${contestId.value}`
      : `/contests/${contestId.value}`,
  )
}

onMounted(() => {
  void load()
})
</script>

<template>
  <SubmissionResultPage
    :submission="displaySubmission"
    :loading="loading"
    :polling-stopped="pollingStopped"
    :back-label="backLabel"
    :refreshing="loading"
    @refresh="refreshNow"
    @back="back"
  />
</template>
