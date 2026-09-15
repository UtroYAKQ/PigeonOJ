<script setup lang="ts">
/**
 * 管理视角 · 提交评测详情（复用组件，两个上下文路由）：
 * 题目管理 /admin/problems/:id/submissions/:sid、提交查看 /admin/submissions/problems/:problemId/submissions/:sid。
 * 经题目上下文统一入口读取（管理权限 + 归属校验，docs/contracts/judge.md）；
 * 返回与面包屑按上下文挂回（提交查看上下文经 meta.backFallback 声明，不入题目管理动线）。
 * 轮询与渲染经 useSubmissionDetail + SubmissionResultView 复用（H4 收敛）。
 */
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { getProblemSubmission } from '@/api/problems'
import SubmissionResultView from '@/components/SubmissionResultView.vue'
import { useSubmissionDetail } from '@/composables/useSubmissionDetail'
import { goBackOrFallback } from '@/utils/navigation'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

/** 题目 id：题目管理上下文取 params.id；提交查看上下文取 params.problemId */
const problemId = String(route.params.problemId ?? route.params.id)

const { submission, loading, pollingStopped, statusLabel, showScoreBox, load, refreshNow } =
  useSubmissionDetail(() => getProblemSubmission(problemId, String(route.params.sid)))

/** 返回按钮文案：提交查看上下文回提交查看，缺省回提交列表 */
const backLabel = computed(() =>
  route.meta.backLabelKey ? t(String(route.meta.backLabelKey)) : t('problems.submissionsManage.backToList'),
)

/** 返回来源工作台：提交查看上下文按 meta.backFallback 回提交查看，其余回题目提交列表 */
function back() {
  goBackOrFallback(
    router,
    String(route.meta.backFallback ?? `/admin/problems/${problemId}/submissions`),
  )
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