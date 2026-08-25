<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NTag } from 'naive-ui'

import { getProblem } from '@/api/problems'
import { message } from '@/utils/feedback'
import { goBackOrFallback } from '@/utils/navigation'
import { problemStatusTagType, problemStatusLabelKey } from '@/constants/problemStatus'
import MarkdownView from '@/components/MarkdownView.vue'
import ProblemSamples from '@/components/ProblemSamples.vue'
import type { ProblemDetailEx } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const problem = ref<ProblemDetailEx | null>(null)
const loading = ref(false)

/** 返回题目管理：来源优先（如从列表筛选态进入），直达打开时兜底固定路径 */
function backToManage() {
  goBackOrFallback(router, '/admin/problems')
}

async function load() {
  loading.value = true
  try {
    problem.value = await getProblem(String(route.params.id))
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="problem-preview">
    <n-spin :show="loading">
      <n-card v-if="problem" :bordered="false" content-style="padding: 24px;">
        <template #header>
          <div class="preview-head">
            <h2 class="preview-head__title">{{ problem.title }}</h2>
            <div class="preview-head__meta">
              <span>{{ problem.time_limit_ms }} ms</span>
              <span>{{ problem.memory_limit_mb }} MB</span>
              <n-tag size="small" round :type="problemStatusTagType(problem.status)">
                {{ t(problemStatusLabelKey[problem.status] ?? problem.status) }}
              </n-tag>
              <n-tag v-if="problem.visibility !== 'public'" size="small" round>
                {{ t(`problems.visibility.${problem.visibility}`) }}
              </n-tag>
              <n-tag
                v-if="problem.needs_reverification"
                size="small"
                round
                type="warning"
              >
                {{ t('problems.preview.needsReverification') }}
              </n-tag>
              <n-tag v-for="tag in problem.tags" :key="tag" size="small" round>{{ tag }}</n-tag>
            </div>
          </div>
        </template>
        <template #header-extra>
          <n-button secondary @click="backToManage">
            {{ t('problems.preview.backToList') }}
          </n-button>
        </template>

        <MarkdownView :source="problem.description" />

        <h3 class="preview-subtitle">{{ t('problems.detail.inputDescription') }}</h3>
        <MarkdownView :source="problem.input_description || ''" />

        <h3 class="preview-subtitle">{{ t('problems.detail.outputDescription') }}</h3>
        <MarkdownView :source="problem.output_description || ''" />

        <h3 class="preview-subtitle">{{ t('problems.detail.samples') }}</h3>
        <ProblemSamples :samples="problem.samples" />

        <template v-if="problem.solution">
          <h3 class="preview-subtitle">{{ t('problems.detail.solution') }}</h3>
          <MarkdownView :source="problem.solution" />
        </template>
      </n-card>
      <n-empty
        v-else-if="!loading"
        :description="t('problems.detail.loadFailed')"
        style="margin: 80px 0"
      >
        <template #extra>
          <n-button @click="backToManage">
            {{ t('problems.preview.backToList') }}
          </n-button>
        </template>
      </n-empty>
    </n-spin>
  </div>
</template>

<style scoped>
.problem-preview {
  max-width: 960px;
  margin: 0 auto;
}
.preview-head__title {
  margin: 0;
  font-size: 18px;
  line-height: 1.35;
}
.preview-head__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  color: var(--app-text-secondary);
  font-size: 12px;
}
.preview-subtitle {
  margin: 20px 0 8px;
  padding-top: 14px;
  border-top: 1px solid var(--app-border);
  font-size: 15px;
}
</style>
