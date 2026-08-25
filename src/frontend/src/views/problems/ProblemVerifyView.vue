<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import { getProblem } from '@/api/problems'
import { message } from '@/utils/feedback'
import type { ProblemDetailEx } from '@/types'
import VerifyPublishPanel from '@/components/problem/VerifyPublishPanel.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const loading = ref(false)
const problemId = String(route.params.id)
/** 完整详情（含验题状态），供「验题与发布」面板使用 */
const detail = ref<ProblemDetailEx | null>(null)
/** 面板实例：发布按钮在向导底栏，动作与门禁状态经 expose 提升 */
const verifyPanel = ref<InstanceType<typeof VerifyPublishPanel> | null>(null)
const publishing = computed(() => verifyPanel.value?.publishing ?? false)
const publishBlocked = computed(() => verifyPanel.value?.blocked ?? true)

function onPublish() {
  verifyPanel.value?.publish()
}

async function loadExisting() {
  loading.value = true
  try {
    const loaded: ProblemDetailEx = await getProblem(problemId)
    if (!loaded.can_manage) throw new Error(t('problems.create.noPermission'))
    detail.value = loaded
  } catch (error) {
    message.error(error instanceof Error ? error.message : t('problems.detail.loadFailed'))
    router.push('/admin/problems')
  } finally {
    loading.value = false
  }
}

function goPrev() {
  router.push(`/admin/problems/${problemId}/edit/cases`)
}
function cancelEdit() {
  // 未发布离开：草稿保留，可随时从管理工作台继续
  router.push('/admin/problems')
}
function onPublished() {
  // 发布成功后回到管理工作台（面板内已提示；前台详情页不承载管理动线）
  router.push('/admin/problems')
}

onMounted(loadExisting)
</script>

<template>
  <div class="page-fill">
    <n-card :bordered="false">
      <template #header>
        <div class="card-head">
          <span>{{ t('problems.wizard.verifyPublish') }}</span>
          <!-- 向导导航收进卡片头：上一步 / 发布 / 取消，无需滚动即可见 -->
          <div class="card-head__actions">
            <n-button size="small" :disabled="loading" @click="goPrev">
              {{ t('problems.wizard.prev') }}
            </n-button>
            <n-tooltip trigger="hover" placement="top" :disabled="!publishBlocked">
              <template #trigger>
                <n-button
                  type="primary"
                  size="small"
                  :loading="publishing"
                  :disabled="publishBlocked || loading"
                  @click="onPublish"
                >
                  {{ t('problems.detail.publish') }}
                </n-button>
              </template>
              {{ t('problems.manage.publishNeedVerified') }}
            </n-tooltip>
            <n-button size="small" quaternary @click="cancelEdit">{{ t('action.cancel') }}</n-button>
          </div>
        </div>
      </template>

      <!-- 步骤指示：当前第 3 步 -->
      <n-steps :current="3" size="small" class="wizard-steps">
        <n-step :title="t('problems.wizard.basic')" />
        <n-step :title="t('problems.wizard.cases')" />
        <n-step :title="t('problems.wizard.verifyPublish')" />
      </n-steps>

      <!-- 面板区 flex:1 撑满剩余高度；spin 只包数据区，不截断 page-fill 拉伸链路 -->
      <n-spin :show="loading" class="verify-stage">
        <VerifyPublishPanel
          v-if="detail"
          ref="verifyPanel"
          :problem="detail"
          @refresh="loadExisting"
          @published="onPublished"
        />
      </n-spin>
    </n-card>
  </div>
</template>

<style scoped>
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}
.card-head__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
/* 面板区：flex 拉伸链 stage → spin-content → vp-split 逐层吃满剩余高度。
   不用 height:100%（百分比高度在纯 flex 分配高度的父级下解析不可靠） */
.verify-stage {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.verify-stage :deep(.n-spin-content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.verify-stage :deep(.vp-split) {
  flex: 1;
  min-height: 0;
}
</style>
