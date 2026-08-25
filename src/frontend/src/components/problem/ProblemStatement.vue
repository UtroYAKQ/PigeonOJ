<script setup lang="ts">
/**
 * 题面正文：描述 / 输入输出说明 / 展示样例 / 官方题解（可选）。
 * 题目详情页、管理预览页、验题面板三处共用；样例统一走 ProblemSamples，
 * 保证「复制输入」等交互全站一致。
 */
import { useI18n } from 'vue-i18n'

import MarkdownView from '@/components/MarkdownView.vue'
import ProblemSamples from '@/components/ProblemSamples.vue'
import type { ProblemDetail } from '@/types'

withDefaults(
  defineProps<{
    problem: Pick<
      ProblemDetail,
      'description' | 'input_description' | 'output_description' | 'samples' | 'solution'
    >
    /** 是否渲染官方题解分区（solution 为空时始终不渲染） */
    showSolution?: boolean
  }>(),
  { showSolution: true },
)

const { t } = useI18n()
</script>

<template>
  <div class="problem-statement">
    <MarkdownView :source="problem.description" />

    <h3 class="problem-statement__subtitle">{{ t('problems.detail.inputDescription') }}</h3>
    <MarkdownView :source="problem.input_description || ''" />

    <h3 class="problem-statement__subtitle">{{ t('problems.detail.outputDescription') }}</h3>
    <MarkdownView :source="problem.output_description || ''" />

    <h3 class="problem-statement__subtitle">{{ t('problems.detail.samples') }}</h3>
    <ProblemSamples :samples="problem.samples" />

    <template v-if="showSolution && problem.solution">
      <h3 class="problem-statement__subtitle">{{ t('problems.detail.solution') }}</h3>
      <MarkdownView :source="problem.solution" />
    </template>
  </div>
</template>

<style scoped>
.problem-statement__subtitle {
  margin: 20px 0 8px;
  padding-top: 14px;
  border-top: 1px solid var(--app-border);
  font-size: 15px;
}
</style>
