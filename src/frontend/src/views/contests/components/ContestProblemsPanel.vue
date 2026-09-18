<script setup lang="ts">
/**
 * 比赛详情 · 题目面板：比赛题目列表（作答状态 / 题号 / 标题，IOI 赛制带分数列）。
 * 行点击进比赛上下文写题页（frontend.md 路由上下文隔离，导航不跳出当前前缀）。
 */
import { computed, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { DataTableColumns } from 'naive-ui'

import { renderSolveMark } from '@/utils/solveMark'
import type { ContestDetail, ContestProblemItem } from '@/types'

const props = defineProps<{
  detail: ContestDetail
}>()

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

/** 比赛 id：全局路由取 params.id，团队上下文路由取 params.cid */
const contestId = computed(() => String(route.params.cid ?? route.params.id))
const teamId = computed(() => (route.params.teamId ? String(route.params.teamId) : null))
/** 上下文基路径（frontend.md 路由上下文隔离）：团队比赛路由内导航不跳出团队前缀 */
const contextBase = computed(() =>
  teamId.value
    ? `/teams/${teamId.value}/contests/${contestId.value}`
    : `/contests/${contestId.value}`,
)

const problemColumns = computed<DataTableColumns<ContestProblemItem>>(() => [
  {
    // 本人在该场比赛的作答状态（练习 / 验题通过不计入）；悬停查看语义
    title: '',
    key: 'solved',
    width: 72,
    render: (row) => renderSolveMark(t, row.solved),
  },
  {
    title: t('contests.detail.letter'),
    key: 'letter',
    width: 70,
    render: (row) => row.letter ?? '--',
  },
  {
    title: t('problemSets.list.titleLabel'),
    key: 'title',
    minWidth: 280,
    render: (row) => h('strong', null, row.title),
  },
  // ACM 赛制无 IOI 单题分语义（按通过 / 罚时计），分数列仅 IOI 展示
  ...(props.detail.rule_type === 'IOI'
    ? [
        {
          title: t('contests.list.problemScore'),
          key: 'score',
          width: 100,
          render: (row: ContestProblemItem) => (row.score > 0 ? String(row.score) : '--'),
        },
      ]
    : []),
])

function goProblem(row: ContestProblemItem) {
  router.push(`${contextBase.value}/problems/${row.problem_id}`)
}

function problemRowProps(row: ContestProblemItem) {
  return {
    style: 'cursor: pointer;',
    onClick: () => goProblem(row),
  }
}
</script>

<template>
  <div class="pane-scroll">
    <n-alert v-if="!detail.can_view_problems" type="info" :bordered="false">
      {{ t('contests.detail.notVisible') }}
    </n-alert>
    <!-- 空态样板（frontend.md）：与内容区 v-show 互斥切换，空态用全局
         table-fill-empty 在 tab 纵向剩余空间内拉伸居中 -->
    <n-data-table
      v-show="detail.can_view_problems && detail.problems.length"
      :columns="problemColumns"
      :data="detail.problems"
      :bordered="false"
      :bottom-bordered="false"
      :row-props="problemRowProps"
    />
    <div
      v-show="detail.can_view_problems && !detail.problems.length"
      class="table-fill-empty detail-empty"
    >
      <n-empty size="large" :description="t('contests.list.problemsEmpty')" />
    </div>
  </div>
</template>

<style scoped>
/* pane 内滚动区：列表撑满，超出滚动 */
.pane-scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 空态：全局 table-fill-empty 拉伸居中；tab 纵向有界，去掉 320px 下限 */
.detail-empty {
  min-height: 0;
}

/* ---- 窄屏 ---- */
@media (max-width: 900px) {
  .pane-scroll {
    overflow: visible;
  }
}
</style>
