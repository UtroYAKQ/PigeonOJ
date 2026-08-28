<script setup lang="ts">
/**
 * 题面正文：题目背景 / 描述 / 输入输出说明 / 展示样例 / 官方题解（可选）。
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
      'background' | 'description' | 'input_description' | 'output_description' | 'samples' | 'solution'
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
    <template v-if="problem.background">
      <h3 class="problem-statement__subtitle problem-statement__subtitle--first">
        {{ t('problems.detail.background') }}
      </h3>
      <MarkdownView :source="problem.background" />
    </template>

    <h3
      class="problem-statement__subtitle"
      :class="{ 'problem-statement__subtitle--first': !problem.background }"
    >
      {{ t('problems.detail.description') }}
    </h3>
    <MarkdownView :source="problem.description" />

    <h3 class="problem-statement__subtitle">{{ t('problems.detail.inputDescription') }}</h3>
    <MarkdownView :source="problem.input_description || ''" />

    <h3 class="problem-statement__subtitle">{{ t('problems.detail.outputDescription') }}</h3>
    <MarkdownView :source="problem.output_description || ''" />

    <h3
      v-if="problem.samples?.length"
      class="problem-statement__subtitle"
    >
      {{ t('problems.detail.samples') }}
    </h3>
    <ProblemSamples v-if="problem.samples?.length" :samples="problem.samples" />

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
/* 题目背景为题面首个分区：去掉顶部分隔线与间距 */
.problem-statement__subtitle--first {
  margin-top: 0;
  padding-top: 0;
  border-top: none;
}
</style>
