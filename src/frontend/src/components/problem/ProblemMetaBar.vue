<script setup lang="ts">
/**
 * 题目元信息条：标题 + 时间/内存限制 + 状态/可见性/待重验标签 + 标签。
 * 题目详情页、管理预览页、验题面板三处共用，避免各自维护一套 meta 排版。
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { NTag } from 'naive-ui'

import { problemStatusLabelKey, problemStatusTagType } from '@/constants/problemStatus'
import type { ProblemDetail } from '@/types'

const props = defineProps<{
  problem: Pick<
    ProblemDetail,
    | 'title'
    | 'time_limit_ms'
    | 'memory_limit_mb'
    | 'status'
    | 'visibility'
    | 'needs_reverification'
    | 'tags'
    | 'difficulty'
    | 'submission_count'
    | 'accepted_count'
  >
  /** 是否展示标题（卡片头 / 面板首行场景开启） */
  showTitle?: boolean
  /** 已发布时隐藏状态标签（前台详情页口径；预览页始终展示便于管理识别） */
  hidePublishedStatus?: boolean
  /** 展示「需重新验题」警示标签（管理预览页口径） */
  showReverifyTag?: boolean
}>()

const { t } = useI18n()
const statusVisible = computed(
  () => !props.hidePublishedStatus || props.problem.status !== 'published',
)

/** 通过率展示：accepted/submission 百分比；无提交不展示 */
const passRate = computed(() => {
  const total = props.problem.submission_count ?? 0
  if (!total) return null
  return `${Math.round(((props.problem.accepted_count ?? 0) / total) * 100)}%`
})
</script>

<template>
  <div class="problem-meta-bar">
    <h2 v-if="showTitle" class="problem-meta-bar__title">{{ problem.title }}</h2>
    <div class="problem-meta-bar__tags">
      <span>{{ problem.time_limit_ms }} ms</span>
      <span>{{ problem.memory_limit_mb }} MB</span>
      <span v-if="problem.difficulty !== null && problem.difficulty !== undefined">
        {{ t('problems.list.difficulty') }} {{ problem.difficulty }}
      </span>
      <span v-if="passRate"> {{ t('problems.list.passRate') }} {{ passRate }} </span>
      <n-tag v-if="statusVisible" size="small" round :type="problemStatusTagType(problem.status)">
        {{ t(problemStatusLabelKey[problem.status] ?? problem.status) }}
      </n-tag>
      <n-tag v-if="problem.visibility && problem.visibility !== 'public'" size="small" round>
        {{ t(`problems.visibility.${problem.visibility}`) }}
      </n-tag>
      <n-tag
        v-if="showReverifyTag && problem.needs_reverification"
        size="small"
        round
        type="warning"
      >
        {{ t('problems.preview.needsReverification') }}
      </n-tag>
    </div>
    <div v-if="problem.tags?.length" class="problem-meta-bar__tags problem-meta-bar__tags--standalone">
      <n-tag
        v-for="tag in problem.tags"
        :key="tag.id"
        size="small"
        :bordered="false"
        :color="tag.color ? { color: tag.color, textColor: '#fff' } : undefined"
      >
        {{ tag.name }}
      </n-tag>
    </div>
  </div>
</template>

<style scoped>
.problem-meta-bar__title {
  margin: 0;
  font-size: 18px;
  line-height: 1.35;
}
.problem-meta-bar__tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  color: var(--app-text-secondary);
  font-size: 12px;
}
.problem-meta-bar__title + .problem-meta-bar__tags {
  margin-top: 8px;
}
.problem-meta-bar__tags--standalone {
  margin-top: 8px;
}
</style>
