<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { getProblem } from '@/api/problems'
import { message } from '@/utils/feedback'
import { goBackOrFallback } from '@/utils/navigation'
import ProblemMetaBar from '@/components/problem/ProblemMetaBar.vue'
import ProblemStatement from '@/components/problem/ProblemStatement.vue'
import type { ProblemDetailEx } from '@/types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const problem = ref<ProblemDetailEx | null>(null)
const loading = ref(false)

/** 题目 id：题库管理取 params.id；题单管理上下文取 params.problemId（params.id 为题单 id） */
const problemId = computed(() => String(route.params.problemId ?? route.params.id))
/** 题单管理上下文标志（返回文案与兜底路径随之切换） */
const inSetContext = computed(() => Boolean(route.params.setId))

/** 返回来源工作台：题单管理上下文回题单详情，其余回题目管理；直达打开兜底固定路径 */
function backToManage() {
  if (inSetContext.value) {
    goBackOrFallback(router, `/admin/problem-sets/${String(route.params.setId)}`)
    return
  }
  goBackOrFallback(router, '/admin/problems')
}

async function load() {
  loading.value = true
  try {
    problem.value = await getProblem(problemId.value)
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
          <!-- 管理预览：始终展示状态标签，便于识别草稿 / 已归档 -->
          <ProblemMetaBar :problem="problem" show-title show-reverify-tag />
        </template>
        <template #header-extra>
          <n-button secondary @click="backToManage">
            {{ inSetContext ? t('problemSets.detail.backToSet') : t('problems.preview.backToList') }}
          </n-button>
        </template>

        <ProblemStatement :problem="problem" />
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
</style>
